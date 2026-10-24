"""Generate SYNTHETIC anime-viewing survey data for demos and load testing.

Nothing here is measured. The output is a simulation, labelled PROXY in its `source` column so the
app flags it, and it is written to data/synthetic/ (never data/survey/) so a live analysis cannot
mistake it for a real survey. See data/synthetic/README.md for the method and its limits.

Method (a probit / latent-normal model):
  * Each respondent has a latent score per genre,
        z = a_g + b_sg + u_s + trend_g + rho * e_i + sqrt(1 - rho^2) * eta_ig,
    and "watches" the genre when z > 0. e_i and eta_ig are standard normal (truncated at +/-3 so
    no draw is an extreme tail event), so the marginal chance a state-s respondent watches genre
    g is Phi(a_g + b_sg + u_s + trend_g).
  * a_g = Phi^-1(base rate). Base rates keep the genre ordering of AniList popularity in
    data/training/super_training_dataset.csv, rescaled to a plausible 12%-82% range (an assumption).
  * b_sg, the state x genre effect, comes from the Google-Trends `lift` in
    data/training/training_table_title_x_state.csv (winsorised, shrunk, damped) plus normal noise.
    That table is search interest, so this part overlaps the Trends signal the app already uses.
  * u_s, state engagement, comes from the Census urban share plus normal noise.
  * Bad respondents (straight-liners, all-"no") are injected, then removed with a modified z-score
    on genres selected; state x genre indices are winsorised across states with a MAD bound.

Needs numpy (installed with `pip install -e ".[ml]"`). Run from the repo root:
    python scripts/generate_synthetic_survey.py [--respondents 300000] [--seed 20261025]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from statistics import NormalDist

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.census import all_states, resolve_state  # noqa: E402

SUPER_DATASET = ROOT / "data/training/super_training_dataset.csv"
STATE_TABLE = ROOT / "data/training/training_table_title_x_state.csv"
OUT_DIR = ROOT / "data/synthetic"

# The genre vocabulary of the title catalogue (genre_* columns of the training table).
GENRES = [
    "Action", "Comedy", "Drama", "Fantasy", "Adventure", "Romance", "Slice of Life",
    "Supernatural", "Psychological", "Mystery", "Sci-Fi", "Ecchi", "Thriller", "Horror",
    "Sports", "Mecha", "Music",
]  # fmt: skip
WAVES = (2024, 2025, 2026)
CONTENT_TYPE = "anime"

RATE_LOW, RATE_HIGH = 0.12, 0.82  # base watch-rate range the AniList ordering is mapped onto
RHO = 0.35  # share of a respondent's genre answers explained by general engagement
TRUNCATE = 3.0  # standard-normal draws are redrawn beyond +/-3
LIFT_KAPPA = 0.15  # probit shift per robust sigma of (shrunk) Trends lift
LIFT_SHRINK = 5.0  # pseudo-titles pulling a state x genre lift toward 0
CELL_NOISE_SD = 0.12  # random state x genre effect (probit units)
CELL_EFFECT_CAP = 0.45
URBAN_KAPPA = 0.10  # probit shift per sd of urban share
URBAN_Z_CAP = 2.0  # urban-share z-scores are capped so Delhi/Chandigarh are not extreme
STATE_NOISE_SD = 0.08
TREND_SD = 0.04  # per-year drift in a genre's probit level
MAD_BOUND = 3.5  # robust sigmas for winsorising lifts, indices and respondent genre counts
INDEX_FLOOR, INDEX_CEIL = 25.0, 300.0
STRAIGHTLINE_MIN = 15  # ticking this many of the 17 genres is treated as straight-lining
STRAIGHTLINER_SHARE = 0.02
ALL_NO_SHARE = 0.01
MIN_PER_STATE = 400

# The Trends table uses the post-2020 merged territory; the 2011 Census lists the two separately.
MERGED_TERRITORIES = {
    "Dadra and Nagar Haveli and Daman and Diu": ["Dadra and Nagar Haveli", "Daman and Diu"]
}

_NORMAL = NormalDist()


def _slug(genre: str) -> str:
    return genre.lower().replace("-", "_").replace(" ", "_")


def _mad_sigma(values: np.ndarray) -> float:
    return float(1.4826 * np.median(np.abs(values - np.median(values))))


def _truncated_normal(rng: np.random.Generator, shape: tuple[int, ...]) -> np.ndarray:
    draws = rng.standard_normal(shape)
    bad = np.abs(draws) > TRUNCATE
    while bad.any():
        draws[bad] = rng.standard_normal(int(bad.sum()))
        bad = np.abs(draws) > TRUNCATE
    return draws


def base_rates() -> dict[str, float]:
    """Assumed share of viewers who watch each genre, ordered like AniList popularity."""
    share = dict.fromkeys(GENRES, 0.0)
    total = 0.0
    with SUPER_DATASET.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if not row["category"].startswith("anime"):
                continue
            popularity = float(row["popularity"] or 0)
            total += popularity
            for genre in (row["genres"] or "").split("|"):
                if genre in share:
                    share[genre] += popularity
    low, high = min(share.values()), max(share.values())
    if total == 0 or high == low:
        raise SystemExit(f"no usable anime genre popularity in {SUPER_DATASET}")
    return {
        genre: RATE_LOW + (value - low) / (high - low) * (RATE_HIGH - RATE_LOW)
        for genre, value in share.items()
    }


def trends_effects(states: list[str]) -> tuple[np.ndarray, dict]:
    """State x genre effect z-scores from the Trends `lift` table (shrunk), plus an audit note."""
    rows = []
    unmapped: set[str] = set()
    with STATE_TABLE.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            flags = [row[f"genre_{g}"] == "1" for g in GENRES]
            names = MERGED_TERRITORIES.get(row["state_name"])
            if names is None:
                state = resolve_state(row["state_name"])
                names = [state.name] if state else []
            if not names:
                unmapped.add(row["state_name"])
            rows.extend((name, float(row["lift"]), flags) for name in names)
    lifts = np.array([lift for _, lift, _ in rows])
    centre, sigma = float(np.median(lifts)), _mad_sigma(lifts)
    low, high = centre - MAD_BOUND * sigma, centre + MAD_BOUND * sigma
    clipped = int(((lifts < low) | (lifts > high)).sum())
    index = {name: i for i, name in enumerate(states)}
    total = np.zeros((len(states), len(GENRES)))
    count = np.zeros((len(states), len(GENRES)))
    for name, lift, flags in rows:
        if name not in index:
            continue
        mask = np.array(flags)
        total[index[name], mask] += min(max(lift, low), high) - centre
        count[index[name], mask] += 1
    z = total / (count + LIFT_SHRINK) / sigma
    note = {
        "rows": len(rows),
        "lift_winsor_bounds": [round(low, 3), round(high, 3)],
        "lifts_winsorised": clipped,
        "states_without_trends_rows": sorted(set(states) - {name for name, *_ in rows}),
        "unmapped_state_names": sorted(unmapped),
    }
    return z, note


@dataclass
class Synthetic:
    states: list[str]
    respondent_wave: np.ndarray  # wave year per kept respondent
    respondent_state: np.ndarray  # state index per kept respondent
    respondent_flags: np.ndarray  # kept respondents x genres, 0/1
    rows: list[dict]  # loader-schema affinity rows
    audit: dict = field(default_factory=dict)


def generate(
    total_respondents: int = 300_000, seed: int = 20261025, min_per_state: int = MIN_PER_STATE
) -> Synthetic:
    rng = np.random.default_rng(seed)
    profiles = all_states()
    states = list(profiles)
    population = np.array([profiles[s].population for s in states], dtype=float)
    urban = np.array([profiles[s].urban_pct for s in states])
    a = np.array([_NORMAL.inv_cdf(rate) for rate in base_rates().values()])

    trends_z, trends_note = trends_effects(states)
    cell = np.clip(
        LIFT_KAPPA * trends_z + rng.normal(0, CELL_NOISE_SD, trends_z.shape),
        -CELL_EFFECT_CAP,
        CELL_EFFECT_CAP,
    )
    engagement = URBAN_KAPPA * np.clip(
        (urban - urban.mean()) / urban.std(), -URBAN_Z_CAP, URBAN_Z_CAP
    ) + rng.normal(0, STATE_NOISE_SD, len(states))
    trend = rng.normal(0, TREND_SD, len(GENRES))

    per_wave = total_respondents // len(WAVES)
    weight = np.sqrt(population)
    n_state = np.maximum(min_per_state, np.rint(per_wave * weight / weight.sum()).astype(int))

    waves, state_ids, flag_blocks = [], [], []
    audit_waves = []
    rows: list[dict] = []
    for k, year in enumerate(WAVES):
        shift = a[None, :] + cell + engagement[:, None] + trend[None, :] * (k - 1)
        block_flags, block_state = [], []
        for s, n in enumerate(n_state):
            e = _truncated_normal(rng, (n, 1))
            eta = _truncated_normal(rng, (n, len(GENRES)))
            z = shift[s][None, :] + RHO * e + math.sqrt(1 - RHO**2) * eta
            block_flags.append((z > 0).astype(np.uint8))
            block_state.append(np.full(n, s))
        flags = np.vstack(block_flags)
        who = np.concatenate(block_state)

        # Contamination: straight-liners tick (almost) everything, some respondents tick nothing.
        n_all = len(flags)
        picks = rng.permutation(n_all)
        n_line, n_none = int(STRAIGHTLINER_SHARE * n_all), int(ALL_NO_SHARE * n_all)
        injected = np.zeros(n_all, dtype=bool)
        for index in picks[:n_line]:
            flags[index] = 1
            flags[index, rng.choice(len(GENRES), rng.integers(0, 3), replace=False)] = 0
        flags[picks[n_line : n_line + n_none]] = 0
        injected[picks[: n_line + n_none]] = True

        # Cleaning: drop all-"no" answers, straight-liners and genre counts that are robust-z
        # outliers.
        counts = flags.sum(axis=1).astype(float)
        mad = np.median(np.abs(counts - np.median(counts)))
        robust_z = 0.6745 * (counts - np.median(counts)) / mad if mad else np.zeros_like(counts)
        keep = (counts > 0) & (counts < STRAIGHTLINE_MIN) & (np.abs(robust_z) <= MAD_BOUND)
        removed_injected, removed_genuine = (
            int((~keep & injected).sum()),
            int((~keep & ~injected).sum()),
        )
        flags, who = flags[keep], who[keep]
        waves.append(np.full(len(flags), year))
        state_ids.append(who)
        flag_blocks.append(flags)

        n_clean = np.bincount(who, minlength=len(states))
        rate = np.vstack([flags[who == s].mean(axis=0) for s in range(len(states))])
        national = (population[:, None] * rate).sum(axis=0) / population.sum()
        index = 100 * rate / national[None, :]
        winsorised = 0
        for g in range(len(GENRES)):
            centre, sigma = np.median(index[:, g]), _mad_sigma(index[:, g])
            low = max(INDEX_FLOOR, centre - MAD_BOUND * sigma)
            high = min(INDEX_CEIL, centre + MAD_BOUND * sigma)
            winsorised += int(((index[:, g] < low) | (index[:, g] > high)).sum())
            index[:, g] = np.clip(index[:, g], low, high)
        label = f"PROXY synthetic: probit-normal simulation, seed {seed}; not measured data"
        for s, name in enumerate(states):
            for g, genre in enumerate(GENRES):
                rows.append(_row(name, genre, index[s, g], int(n_clean[s]), year, label))
        national_index = 100 * national / national.mean()
        for g, genre in enumerate(GENRES):
            rows.append(_row("India", genre, national_index[g], int(n_clean.sum()), year, label))
        audit_waves.append(
            {
                "year": year,
                "generated": n_all,
                "straight_liners_injected": n_line,
                "all_no_injected": n_none,
                "removed": int((~keep).sum()),
                "removed_injected": removed_injected,
                "removed_genuine": removed_genuine,
                "injected_missed": int((keep & injected).sum()),
                "kept": int(keep.sum()),
                "indices_winsorised": winsorised,
                "index_min": round(float(index.min()), 2),
                "index_max": round(float(index.max()), 2),
                "national_watch_rate": {
                    genre: round(float(national[g]), 3) for g, genre in enumerate(GENRES)
                },
            }
        )

    audit = {
        "seed": seed,
        "respondents_requested": total_respondents,
        "min_per_state": min_per_state,
        "base_rates_assumed": {g: round(r, 3) for g, r in base_rates().items()},
        "trends_input": trends_note,
        "waves": audit_waves,
    }
    return Synthetic(
        states,
        np.concatenate(waves),
        np.concatenate(state_ids),
        np.vstack(flag_blocks),
        rows,
        audit,
    )


def _row(state: str, genre: str, index: float, n: int, year: int, source: str) -> dict:
    return {
        "state": state,
        "genre": genre.lower(),
        "content_type": CONTENT_TYPE,
        "index": round(float(index), 2),
        "sample_size": n,
        "year": year,
        "source": source,
    }


def write(result: Synthetic, out_dir: Path = OUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    fields = ["state", "genre", "content_type", "index", "sample_size", "year", "source"]
    with (out_dir / "synthetic_viewing_affinity.csv").open("w", encoding="utf-8", newline="") as f:
        f.write(
            "# SYNTHETIC: simulated, not measured. Do not copy into data/survey/ for real runs.\n"
        )
        f.write("# Method and limits: data/synthetic/README.md\n")
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(result.rows)
    # A subfolder: the survey loader reads every *.csv directly inside its folder and would reject
    # this respondent-level file as a malformed survey.
    (out_dir / "microdata").mkdir(exist_ok=True)
    with (out_dir / "microdata" / "synthetic_survey_respondents.csv").open(
        "w", encoding="utf-8", newline=""
    ) as f:
        writer = csv.writer(f)
        writer.writerow(["respondent_id", "year", "state", *(_slug(g) for g in GENRES)])
        for i, (year, s, flags) in enumerate(
            zip(
                result.respondent_wave,
                result.respondent_state,
                result.respondent_flags,
                strict=True,
            )
        ):
            writer.writerow([f"S{i:07d}", year, result.states[s], *flags.tolist()])
    (out_dir / "synthetic_survey_audit.json").write_text(
        json.dumps(result.audit, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--respondents", type=int, default=300_000, help="total across waves")
    parser.add_argument("--seed", type=int, default=20261025)
    args = parser.parse_args()
    result = generate(args.respondents, args.seed)
    write(result)
    kept = len(result.respondent_flags)
    print(f"wrote {len(result.rows)} affinity rows and {kept:,} respondents to {OUT_DIR}")


if __name__ == "__main__":
    main()
