"""Evaluation per the architecture: rank correlation, top-3 regional hit rate, baseline uplift."""
import numpy as np
import pandas as pd
from scipy.stats import spearmanr


def per_title_metrics(rows: pd.DataFrame, pred: np.ndarray, k: int = 3, target: str = "share") -> pd.DataFrame:
    """For each title: Spearman across states and whether the top-k states overlap the truth."""
    df = rows[["title_id", "state", target]].rename(columns={target: "share"}).assign(pred=pred)
    out = []
    for tid, g in df.groupby("title_id"):
        if len(g) < k + 1 or g["share"].nunique() < 2:
            continue
        rho = spearmanr(g["pred"], g["share"]).statistic
        true_top = set(g.nlargest(k, "share")["state"])
        pred_top = set(g.nlargest(k, "pred")["state"])
        out.append({"title_id": tid, "spearman": 0.0 if np.isnan(rho) else rho,
                    "top3_hit": len(true_top & pred_top) / k})
    return pd.DataFrame(out)


def summarize(metrics: pd.DataFrame, n_boot: int = 1000, seed: int = 0) -> dict:
    """Mean and 95% bootstrap interval over titles (test sets are small)."""
    rng = np.random.default_rng(seed)
    res = {"n_titles": len(metrics)}
    for col in ("spearman", "top3_hit"):
        vals = metrics[col].to_numpy()
        boots = [rng.choice(vals, len(vals)).mean() for _ in range(n_boot)] if len(vals) else [np.nan]
        res[col] = {"mean": float(np.mean(vals)) if len(vals) else float("nan"),
                    "ci95": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]}
    return res
