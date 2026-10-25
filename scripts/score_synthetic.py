"""Score every synthetic row on the five market-potential factors (0-1) and their weighted average.

    PYTHONPATH=.packages py -3.12 scripts/score_synthetic.py

Per-row factor mapping (rows carry no title metadata, so some factors reuse the pipeline's own
deterministic demo-adapter signals keyed by a state|genre|format pseudo-title):
  content_fit            pipeline formula with full metadata: 0.77 + genre bonus + language bonus
  demand_momentum        mean(google_trends interest, momentum, wikimedia curiosity) demo signals
  regional_opportunity   census-weighted state-demand target (the trained regional model's label)
  engagement_quality     mean(youtube attention, engagement quality, velocity) demo signals
  comparable_performance mean India performance of the labelled real titles sharing the genre
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.census import FORMATS, GENRES, STATES  # noqa: E402
from app.ml.corpus import load_labeled_corpus  # noqa: E402
from app.ml.regional import resolve_genre  # noqa: E402
from app.services.scoring import WEIGHTS  # noqa: E402
from app.services.sources.demo import stable_number  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "data" / "synthetic"
BONUS_GENRES = {"action", "fantasy", "romance", "mystery_thriller", "comedy"}  # thriller counted
FACTORS = list(WEIGHTS)


def cell_signals(state: str, genre: str, fmt: str) -> tuple[float, float]:
    """Demand and engagement in 0-1, using the demo adapters' formulas and seeds."""
    boost = 0.05 if genre in BONUS_GENRES else 0.0

    def value(source: str) -> float:
        return min(0.95, stable_number(f"{state}|{genre}|{fmt}|{source}", 0.48, 0.88) + boost)

    def extra(source: str, key: str, low: float, high: float) -> float:
        return stable_number(f"{state}|{genre}|{fmt}|{source}{key}", low, high)

    demand = np.mean([value("google_trends"), extra("google_trends", "momentum", 0.35, 0.9), value("wikimedia")])
    engagement = np.mean(
        [value("youtube"), extra("youtube", "engagement", 0.4, 0.88), extra("youtube", "velocity", 0.3, 0.9)]
    )
    return float(demand), float(engagement)


def main() -> None:
    d = np.load(DATA / "market_synthetic.npz")
    state, genre, fmt = d["state"].astype(int), d["genre"].astype(int), d["format"].astype(int)
    n = len(state)

    demand_t = np.zeros((len(STATES), len(GENRES), len(FORMATS)))
    engage_t = np.zeros_like(demand_t)
    for s in range(len(STATES)):
        for g in range(len(GENRES)):
            for f in range(len(FORMATS)):
                demand_t[s, g, f], engage_t[s, g, f] = cell_signals(STATES[s], GENRES[g], FORMATS[f])

    corpus = load_labeled_corpus()
    overall = np.mean([r["performance"] for r in corpus])
    per_genre = np.full(len(GENRES), overall)
    for gi, g in enumerate(GENRES):
        vals = [r["performance"] for r in corpus if any(resolve_genre(t) == g for t in r["genres"])]
        if vals:
            per_genre[gi] = np.mean(vals)

    bonus = np.array([g in BONUS_GENRES for g in GENRES], dtype=float)
    factors = {
        "content_fit": np.clip(0.77 + 0.07 * bonus[genre] + np.minimum(0.06, 0.015 * d["language_match"]), 0, 1),
        "demand_momentum": demand_t[state, genre, fmt],
        "regional_opportunity": np.clip(d["target"].astype(np.float64) / 100, 0, 1),
        "engagement_quality": engage_t[state, genre, fmt],
        "comparable_performance": np.clip(per_genre[genre] / 100 * (0.65 + 0.35 * 0.6), 0, 1),
    }
    weights = np.array([WEIGHTS[k] for k in FACTORS])
    matrix = np.stack([factors[k] for k in FACTORS], axis=1).astype(np.float32)
    weighted = matrix.astype(np.float64) @ weights  # 0-1
    percent = weighted * 100

    # Consistency checks
    checks = {
        "weights_sum_to_1": bool(abs(weights.sum() - 1) < 1e-12),
        "all_factors_within_0_1": bool(matrix.min() >= 0 and matrix.max() <= 1),
        "no_nan_or_inf": bool(np.isfinite(matrix).all()),
        "weighted_average_within_factor_range": bool(
            (weighted >= matrix.min(axis=1) - 1e-6).all() and (weighted <= matrix.max(axis=1) + 1e-6).all()
        ),
        "max_abs_recompute_error_pct": float(np.abs(sum(WEIGHTS[k] * factors[k] for k in FACTORS) * 100 - percent).max()),
    }

    def stats(mask: np.ndarray) -> dict:
        return {
            "rows": int(mask.sum()),
            "factors": {k: round(float(matrix[mask, i].mean()), 4) for i, k in enumerate(FACTORS)},
            "weighted_average_pct": round(float(percent[mask].mean()), 2),
        }

    summary = {
        "rows": n,
        "weights": WEIGHTS,
        "overall": {**stats(np.ones(n, bool)), "weighted_average_pct_sd": round(float(percent.std()), 2),
                    "weighted_average_pct_min": round(float(percent.min()), 2),
                    "weighted_average_pct_max": round(float(percent.max()), 2)},
        "by_state": {s: stats(state == i) for i, s in enumerate(STATES)},
        "by_format": {f: stats(fmt == i) for i, f in enumerate(FORMATS)},
        "by_genre": {g: stats(genre == i) for i, g in enumerate(GENRES)},
        "consistency_checks": checks,
        "caveat": "demand_momentum and engagement_quality are the offline demo-adapter signals; comparable_performance uses only 27 real titles.",
    }
    (DATA / "factor_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    np.savez_compressed(DATA / "market_factors.npz", factors=matrix, weighted_average=weighted.astype(np.float32),
                        factor_names=np.array(FACTORS))
    head = "state,genre,format," + ",".join(FACTORS) + ",weighted_average_pct"
    rows = [head] + [
        f"{STATES[state[i]]},{GENRES[genre[i]]},{FORMATS[fmt[i]]},"
        + ",".join(f"{matrix[i, j]:.4f}" for j in range(len(FACTORS)))
        + f",{percent[i]:.2f}"
        for i in range(5000)
    ]
    (DATA / "factors_sample_5000.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(json.dumps({"overall": summary["overall"], "checks": checks}, indent=1))
    for s, v in summary["by_state"].items():
        print(f"{s:14s} {v['rows']:>9,} rows  {v['weighted_average_pct']:.2f}%")


if __name__ == "__main__":
    main()
