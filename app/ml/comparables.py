"""Comparable retrieval: stage 1 semantic candidates, stage 2 re-rank.

Stage 1 is cosine similarity over synopsis embeddings (pgvector in production; the
same maths in memory here). Stage 2 re-ranks by genre, format and lifecycle.
Rules that prevent leakage: a comparable must be released before the target and
belong to a different franchise.
"""
import numpy as np
import pandas as pd

CANDIDATES = 20
TOP_K = 5


def _jaccard(a: list[str], b: list[str]) -> float:
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a | b else 0.0


class ComparableIndex:
    def __init__(self, titles: pd.DataFrame, embeddings: np.ndarray):
        """`titles` rows align with `embeddings` (unit vectors); only these can be comparables."""
        self.titles = titles.reset_index(drop=True)
        self.emb = embeddings

    def find(self, target: pd.Series, target_emb: np.ndarray, k: int = TOP_K) -> list[tuple[int, float]]:
        """[(index into self.titles, combined score)] best first."""
        sims = self.emb @ target_emb
        valid = (self.titles["release_date"] < target["release_date"]) & \
                (self.titles["franchise_id"] != target["franchise_id"])
        sims = np.where(valid.to_numpy(), sims, -np.inf)
        cand = np.argsort(-sims)[:CANDIDATES]
        scored = []
        for i in cand:
            if not np.isfinite(sims[i]):
                continue
            row = self.titles.iloc[i]
            years = abs((target["release_date"] - row["release_date"]).days) / 365
            score = (0.6 * sims[i] + 0.25 * _jaccard(target["genres"], row["genres"])
                     + 0.1 * float(row["format"] == target["format"]) + 0.05 / (1 + years))
            scored.append((int(i), float(score), float(sims[i])))
        scored.sort(key=lambda x: -x[1])
        return [(i, s, sim) for i, s, sim in scored[:k]]


def comparable_features(index: ComparableIndex, targets: pd.DataFrame, target_emb: np.ndarray,
                        labels: pd.DataFrame, states: list[str],
                        value: str = "share") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per (title, state): similarity-weighted mean of `value` over the comparables (column cmp_share).

    Also returns per-title stats (cmp_count, cmp_sim) used by the confidence model.
    """
    share = labels.pivot_table(index="title_id", columns="state", values=value)
    rows, stats = [], []
    for pos, (_, t) in enumerate(targets.iterrows()):
        found = index.find(t, target_emb[pos])
        ids = [index.titles.iloc[i]["title_id"] for i, _, _ in found]
        w = np.array([max(sim, 1e-6) for _, _, sim in found])
        stats.append({"title_id": t["title_id"], "cmp_count": len(found),
                      "cmp_sim": float(w.mean()) if len(found) else 0.0})
        for s in states:
            vals = np.array([share.at[i, s] if i in share.index and s in share.columns else np.nan for i in ids])
            ok = ~np.isnan(vals)
            rows.append({"title_id": t["title_id"], "state": s,
                         "cmp_share": float((vals[ok] * w[ok]).sum() / w[ok].sum()) if ok.any() else np.nan})
    return pd.DataFrame(rows), pd.DataFrame(stats)
