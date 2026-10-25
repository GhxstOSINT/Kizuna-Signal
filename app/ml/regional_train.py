"""Generate the census-weighted synthetic dataset and train the state-demand model (needs numpy).

    PYTHONPATH=.packages py -3.12 scripts/train_regional.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from app.ml import regional
from app.ml.census import (
    BUDGET_EFFECT,
    BUDGETS,
    CENSUS,
    CENSUS_META,
    FORMAT_AFFINITY,
    FORMATS,
    GENRE_AFFINITY,
    GENRES,
    PLATFORM_EFFECT,
    PLATFORMS,
    STATES,
    TARGET_MEAN,
    TARGET_SD,
    TOP_STATE_INFLATION,
    inflation,
    population_weights,
    reach_index,
    top_states,
)
from app.ml.regional import (
    N_FEATURES,
    O_AGE,
    O_LANG,
    resolve_genre,
)

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "synthetic"
FORMAT_MAIN = {"film": 0.0, "series": 1.0, "soap_opera": -1.0}
FORMAT_GIVEN_GENRE = {
    "family_drama": [0.10, 0.30, 0.60],
    "musical_romance": [0.70, 0.10, 0.20],
}
FORMAT_DEFAULT = [0.35, 0.55, 0.10]
PLATFORM_GIVEN_FORMAT = {  # columns follow PLATFORMS: ott, theatrical, broadcast_tv
    "film": [0.40, 0.55, 0.05],
    "series": [0.70, 0.00, 0.30],
    "soap_opera": [0.30, 0.00, 0.70],
}
LANGUAGE_OF = {
    "Maharashtra": "Hindi", "Karnataka": "Kannada", "Delhi NCR": "Hindi", "Tamil Nadu": "Tamil",
    "Telangana": "Telugu", "West Bengal": "Bengali", "Kerala": "Malayalam", "Uttar Pradesh": "Hindi",
}


def real_genre_effects() -> tuple[dict[str, float], np.ndarray, dict]:
    """Anchor to the labelled real titles: shrunken per-genre mean performance and the year spread."""
    from app.ml.corpus import load_labeled_corpus

    rows = load_labeled_corpus()
    overall = np.mean([r["performance"] for r in rows])
    by_genre: dict[str, list[float]] = {g: [] for g in GENRES}
    for r in rows:
        for tag in r["genres"]:
            by_genre[resolve_genre(tag)].append(r["performance"])
    effect, counts = {}, np.ones(len(GENRES))
    for i, g in enumerate(GENRES):
        vals = by_genre[g]
        counts[i] += len(vals)
        shrink = len(vals) / (len(vals) + 5)  # few observations -> pull toward zero
        effect[g] = float(np.clip(0.4 * shrink * (np.mean(vals) - overall), -6, 6)) if vals else 0.0
    ages = np.array([2026 - r["year"] for r in rows], dtype=float)
    return effect, counts, {"age_mean": float(ages.mean()), "age_sd": float(ages.std())}


def generate(n: int, seed: int = 11) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    genre_effect, genre_counts, age_stats = real_genre_effects()

    state = rng.choice(len(STATES), size=n, p=population_weights())  # census-weighted volume
    infl = np.array([inflation(s) for s in STATES])
    # P(genre | state) ~ base popularity * exp(inflated affinity / 10)
    logits = np.zeros((len(STATES), len(GENRES)))
    for si, s in enumerate(STATES):
        for gi, g in enumerate(GENRES):
            logits[si, gi] = np.log(genre_counts[gi]) + infl[si] * GENRE_AFFINITY[s].get(g, 0) / 10
    p_genre = np.exp(logits)
    p_genre /= p_genre.sum(axis=1, keepdims=True)
    cdf = p_genre.cumsum(axis=1)[state]
    genre = (rng.random(n)[:, None] > cdf).sum(axis=1).clip(max=len(GENRES) - 1)

    fmt = np.empty(n, dtype=np.int64)
    for gi, g in enumerate(GENRES):
        mask = genre == gi
        fmt[mask] = rng.choice(len(FORMATS), size=int(mask.sum()), p=FORMAT_GIVEN_GENRE.get(g, FORMAT_DEFAULT))
    platform = np.empty(n, dtype=np.int64)
    for fi, f in enumerate(FORMATS):
        mask = fmt == fi
        platform[mask] = rng.choice(len(PLATFORMS), size=int(mask.sum()), p=PLATFORM_GIVEN_FORMAT[f])
    budget = rng.choice(len(BUDGETS), size=n, p=[0.25, 0.50, 0.25])
    lang_match = (rng.random(n) < 0.5).astype(np.float64)
    age = np.clip(rng.normal(age_stats["age_mean"], age_stats["age_sd"], n), 0, 30)

    pop = np.array([CENSUS[s]["population_m"] for s in STATES])
    reach = np.array([reach_index(s) for s in STATES])
    pop_n, reach_n = pop / pop.max(), reach / reach.max()
    aff_g = np.array([[GENRE_AFFINITY[s].get(g, 0.0) for g in GENRES] for s in STATES])
    aff_f = np.array([[FORMAT_AFFINITY[s].get(f, 0.0) for f in FORMATS] for s in STATES])
    g_eff = np.array([genre_effect[g] for g in GENRES])
    f_main = np.array([FORMAT_MAIN[f] for f in FORMATS])
    p_eff = np.array([PLATFORM_EFFECT[p] for p in PLATFORMS])
    b_eff = np.array([BUDGET_EFFECT[b] for b in BUDGETS])

    raw = (
        55 + 20 * pop_n[state] + 8 * reach_n[state]
        + g_eff[genre]
        + infl[state] * aff_g[state, genre]
        + infl[state] * aff_f[state, fmt]
        + f_main[fmt]
        + p_eff[platform] + np.where(platform == 0, 4 * (reach_n[state] - 0.5), 0.0)
        + b_eff[budget] * (0.5 + 0.5 * reach_n[state])
        + 5 * lang_match
        - 0.15 * age
        + rng.normal(0, 5, n)
    )
    # Normalisation: z-score then rescale onto the legacy 0-100 regional score scale.
    target = np.clip(TARGET_MEAN + TARGET_SD * (raw - raw.mean()) / raw.std(), 0, 100)
    return {
        "state": state.astype(np.int8), "genre": genre.astype(np.int8), "format": fmt.astype(np.int8),
        "platform": platform.astype(np.int8), "budget": budget.astype(np.int8),
        "language_match": lang_match.astype(np.int8), "age": age.astype(np.float32),
        "target": target.astype(np.float32), "_age_stats": age_stats, "_raw_sd": float(raw.std()),
    }


def design(d: dict, sl: slice, norm: dict) -> np.ndarray:
    n = len(d["state"][sl])
    x = np.zeros((n, N_FEATURES))
    s, g, f, p, b = (d[k][sl].astype(np.int64) for k in ("state", "genre", "format", "platform", "budget"))
    # Vectorised equivalent of regional.active_columns (same column order).
    ncols = np.stack(
        [
            np.zeros(n, dtype=np.int64),
            regional.O_STATE + s,
            regional.O_GENRE + g,
            regional.O_FORMAT + f,
            regional.O_PLATFORM + p,
            regional.O_BUDGET + b,
            regional.O_SG + s * regional.NG + g,
            regional.O_SF + s * regional.NF + f,
            regional.O_SP + s * regional.NP + p,
            regional.O_SB + s * regional.NB + b,
        ],
        axis=1,
    )
    x[np.arange(n)[:, None], ncols] = 1.0
    x[:, O_LANG] = (d["language_match"][sl] - norm["language_match"][0]) / norm["language_match"][1]
    x[:, O_AGE] = (d["age"][sl] - norm["age"][0]) / norm["age"][1]
    return x


def train(n_rows: int = 1_500_000, seed: int = 11, ridge: float = 1.0) -> dict:
    started = time.time()
    d = generate(n_rows, seed)
    norm = {
        "age": [float(d["age"].mean()), float(d["age"].std())],
        "language_match": [float(d["language_match"].mean()), float(d["language_match"].std())],
    }
    n = n_rows
    split = int(n * 0.8)  # rows are i.i.d., so a positional split is a random split
    chunk = 100_000
    xtx = np.zeros((N_FEATURES, N_FEATURES))
    xty = np.zeros(N_FEATURES)
    for start in range(0, split, chunk):
        sl = slice(start, min(start + chunk, split))
        x = design(d, sl, norm)
        y = d["target"][sl].astype(np.float64)
        xtx += x.T @ x
        xty += x.T @ y
    penalty = np.eye(N_FEATURES) * ridge
    penalty[0, 0] = 0  # intercept is not penalised
    coef = np.linalg.solve(xtx + penalty, xty)

    errors, ys, preds = [], [], []
    for start in range(split, n, chunk):
        sl = slice(start, min(start + chunk, n))
        pred = np.clip(design(d, sl, norm) @ coef, 0, 100)
        y = d["target"][sl].astype(np.float64)
        errors.append(np.abs(pred - y))
        ys.append(y)
        preds.append(pred)
    err, y, pred = np.concatenate(errors), np.concatenate(ys), np.concatenate(preds)
    r2 = 1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2)

    # State x genre demand map from the generated population (for the dashboard model card).
    profile = {}
    for si, s in enumerate(STATES):
        row = {}
        for gi, g in enumerate(GENRES):
            m = (d["state"] == si) & (d["genre"] == gi)
            row[g] = {"rows": int(m.sum()), "mean_demand": round(float(d["target"][m].mean()), 2)}
        profile[s] = row

    artifact = {
        "model": "ridge-regression on one-hot state/genre/format/platform/budget and pairwise state interactions",
        "model_version": regional.MODEL_VERSION,
        "target": "state demand index, z-scored then rescaled to mean 72 / sd 9 (0-100)",
        "feature_count": N_FEATURES,
        "coefficients": [float(c) for c in coef],
        "normalisation": norm,
        "hyperparameters": {"ridge": ridge, "seed": seed},
        "conformal": {"q80": round(float(np.quantile(err, 0.8)), 3), "q90": round(float(np.quantile(err, 0.9)), 3)},
        "dataset": {
            "rows": n_rows,
            "train_rows": split,
            "holdout_rows": n - split,
            "synthetic": True,
            "generator": "census-weighted parametric simulation, anchored to 27 labelled real titles",
            "state_sampling": "proportional to Census 2011 population",
            "top_states": sorted(top_states()),
            "top_state_affinity_inflation": TOP_STATE_INFLATION,
            "census_note": (
                f"Census 2011 figures ({CENSUS_META.get('status')}) give population, urbanisation, literacy and TV "
                "households only; genre affinities are assumptions."
            ),
            "state_genre_profile": profile,
        },
        "metrics": {
            "evaluation": "20% holdout of the synthetic data (measures fit to the generator, NOT real-world accuracy)",
            "holdout_r2": round(float(r2), 4),
            "holdout_mae": round(float(err.mean()), 3),
            "r2_ceiling": round(1 - (5 / d["_raw_sd"]) ** 2, 4),
            "r2_ceiling_note": "Best possible holdout R2 given the generator's injected noise (sd 5).",
        },
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(DATA_DIR / "market_synthetic.npz", **{k: v for k, v in d.items() if not k.startswith("_")})
    sample = np.column_stack([d[k][:5000] for k in ("state", "genre", "format", "platform", "budget", "language_match", "age", "target")])
    header = "state,genre,format,platform,budget,language_match,age,target_demand"
    lines = [header]
    for r in sample:
        lines.append(
            f"{STATES[int(r[0])]},{GENRES[int(r[1])]},{FORMATS[int(r[2])]},{PLATFORMS[int(r[3])]},"
            f"{BUDGETS[int(r[4])]},{int(r[5])},{r[6]:.1f},{r[7]:.2f}"
        )
    (DATA_DIR / "sample_5000.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    artifact["dataset"]["seconds"] = round(time.time() - started, 1)
    return artifact


def real_data_check(artifact: dict) -> dict:
    """Does the model's national view agree with the 27 real labelled titles? (honest check)"""
    from app.ml.corpus import load_labeled_corpus

    regional._cache = artifact
    weights = dict(zip(STATES, population_weights(), strict=True))
    xs, ys = [], []
    for r in load_labeled_corpus():
        out = regional.predict_states(
            r["genres"] or ["drama"], "film" if r["is_film"] else "series",
            "theatrical" if r["is_film"] else "ott", "medium", [], 2026 - r["year"], LANGUAGE_OF,
        )
        xs.append(sum(weights[s] * v["demand"] for s, v in out.items()))
        ys.append(r["performance"])
    xs, ys = np.array(xs), np.array(ys)
    rank = lambda a: np.argsort(np.argsort(a))  # noqa: E731
    return {
        "titles": len(xs),
        "pearson": round(float(np.corrcoef(xs, ys)[0, 1]), 3),
        "spearman": round(float(np.corrcoef(rank(xs), rank(ys))[0, 1]), 3),
        "note": "Correlation of national model demand with hand-set India performance; small n.",
    }


def main(n_rows: int = 1_500_000) -> dict:
    artifact = train(n_rows)
    artifact["metrics"]["real_data_check"] = real_data_check(artifact)
    regional.ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    regional.ARTIFACT_PATH.write_text(json.dumps(artifact, indent=1), encoding="utf-8")
    return artifact
