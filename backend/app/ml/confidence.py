"""Confidence is a separate output from the prediction (architecture: potential vs confidence).

Factors (each 0-1): data completeness, comparable quality/count, interval width,
and out-of-distribution distance. Output is 0-100 with the factors exposed.
"""

import numpy as np
import pandas as pd

from app.ml.scoring_config import ConfidenceConfig


def title_confidence(
    rows: pd.DataFrame,
    pred: np.ndarray,
    width: np.ndarray,
    n_states: int,
    cmp_stats: pd.DataFrame,
    max_train_sim: dict[str, float],
    cfg: ConfidenceConfig = ConfidenceConfig(),
    scale: float | None = None,
    inputs: float | None = None,
    history: float | None = None,
    disagreement: np.ndarray | None = None,
) -> pd.DataFrame:
    """`scale` replaces the mean prediction as the yardstick for interval width (needed when the
    target is centred on zero, where the mean prediction says nothing about size).

    `inputs` (0-1) is how much of the title's own information was supplied and `history` (0-1) whether
    earlier franchise/studio titles exist; with them completeness varies per title instead of being
    fixed by the number of states scored. `disagreement` is |ridge - xgboost| per row (same units as
    `scale`); without it the agreement factor falls back to the interval factor."""
    df = rows[["title_id"]].assign(pred=pred, width=width)
    if "pre_has_data" in rows:
        df["pre"] = rows["pre_has_data"].to_numpy()
    else:
        df["pre"] = 0.0
    g = (
        df.groupby("title_id")
        .agg(
            n=("pred", "size"), pred=("pred", "mean"), width=("width", "mean"), pre=("pre", "mean")
        )
        .reset_index()
    )
    g = g.merge(cmp_stats, on="title_id", how="left").fillna({"cmp_count": 0, "cmp_sim": 0})
    if inputs is None:
        completeness = 0.5 * (g["n"] / n_states).clip(0, 1) + 0.5 * g["pre"]
    else:
        completeness = 0.5 * inputs + 0.25 * (history or 0.0) + 0.25 * g["pre"]
    comparables = (g["cmp_count"] / 5).clip(0, 1) * g["cmp_sim"].clip(0, 1)
    interval = 1 / (1 + g["width"] / (scale if scale else g["pred"].clip(lower=1e-6)))
    if disagreement is None:
        agreement = interval
    else:
        gap = (
            pd.Series(np.abs(disagreement), index=rows.index)
            .groupby(rows["title_id"].to_numpy())
            .mean()
        )
        agreement = (
            g["title_id"].map(gap).astype(float).pipe(lambda d: 1 / (1 + d / (scale or 1.0)))
        )
    ood = g["title_id"].map(max_train_sim).fillna(0).clip(0, 1)
    score = (
        cfg.completeness * completeness
        + cfg.comparables * comparables
        + cfg.agreement * agreement
        + cfg.interval * interval
        + cfg.out_of_distribution * ood
    )
    return pd.DataFrame(
        {
            "title_id": g["title_id"],
            "confidence": (100 * score).round(1),
            "completeness": completeness,
            "comparables": comparables,
            "agreement": agreement,
            "interval": interval,
            "ood": ood,
        }
    )
