"""Synthetic title x state labels for cells Google Trends left empty.

Small states return no Trends data for most titles (Lakshadweep has 10 of 62), so their state effect and
their lift rows rest on few, selected titles. For each labelled title and each missing state we fill the
title-centred log share (`dlog`) with a weighted average of two kinds of evidence:

* content neighbours: lift of the most similar OTHER training titles that do have data in that state
  (weight = similarity ** power, similarity = synopsis cosine and genre/theme Jaccard);
* region neighbours: the title's own lift in states that share its language (weight 1) or zone (weight 0.5).

Each estimate is shrunk towards 0 (a typical anime in that state) by n/(n+k), so thin evidence gives a
small lift, not an invented one. Cells with too little support are not filled. Synthetic rows carry a low
sample weight, are never used for validation, never feed history features, and are built only from the
titles in the training split, so out-of-fold metrics stay honest.

This adds no new information: it spreads what the observed cells say into the empty ones. It can reduce
the pull of sparse-state noise; it cannot fix a state where nobody observed anything.
"""
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SyntheticConfig:
    version: str = "synthetic-v1"
    weight: float = 0.3  # sample weight of a synthetic row (real rows = 1)
    neighbours: int = 8  # content neighbours per cell
    sim_power: float = 3.0  # sharpens the similarity weights
    cosine_share: float = 0.5  # similarity = share * cosine + (1 - share) * Jaccard
    content_share: float = 0.6  # blend of the two estimates
    region_share: float = 0.4
    content_prior: float = 2.0  # shrinkage k: estimate * n_eff / (n_eff + k)
    region_prior: float = 2.0
    min_support: float = 1.5  # a cell needs content or region support of at least this
    language_weight: float = 1.0
    zone_weight: float = 0.5


def as_dict(cfg: SyntheticConfig) -> dict:
    return asdict(cfg)


def _jaccard_matrix(sets: list[set]) -> np.ndarray:
    n = len(sets)
    out = np.zeros((n, n))
    for i in range(n):
        for j in range(i, n):
            u = len(sets[i] | sets[j])
            out[i, j] = out[j, i] = len(sets[i] & sets[j]) / u if u else 0.0
    return out


def _region_weights(state_ctx: pd.DataFrame, states: list[str], cfg: SyntheticConfig) -> np.ndarray:
    ctx = state_ctx.set_index("state").reindex(states).fillna(0)
    lang = ctx[[c for c in ctx if c.startswith("state_lang_")]].to_numpy(float)
    zone = ctx[[c for c in ctx if c.startswith("state_zone_")]].to_numpy(float)
    w = np.maximum(cfg.language_weight * (lang @ lang.T > 0), cfg.zone_weight * (zone @ zone.T > 0))
    np.fill_diagonal(w, 0.0)
    return w


def _n_eff(w: np.ndarray) -> float:
    return float(w.sum() ** 2 / (w ** 2).sum()) if len(w) and (w ** 2).sum() > 0 else 0.0


def synthesize(labels: pd.DataFrame, titles: pd.DataFrame, emb: np.ndarray, states: list[str],
               state_ctx: pd.DataFrame, effect: pd.Series, cfg: SyntheticConfig = SyntheticConfig()) -> pd.DataFrame:
    """Synthetic rows for the missing cells of `titles`.

    `labels` needs title_id, state, log_share, dlog (real rows of the training titles only); `titles` and `emb`
    align row for row; `effect` is the state effect from those same labels. Returns title_id, state, share,
    log_share, dlog, n_content, n_region.
    """
    ids = titles["title_id"].tolist()
    pos = {t: i for i, t in enumerate(ids)}
    sidx = {s: j for j, s in enumerate(states)}
    eff = effect.reindex(states).fillna(0.0).to_numpy()

    lift = np.full((len(ids), len(states)), np.nan)  # observed lift = dlog - state effect
    for t, s, d in zip(labels["title_id"], labels["state"], labels["dlog"]):
        if t in pos and s in sidx:
            lift[pos[t], sidx[s]] = d - eff[sidx[s]]
    seen = ~np.isnan(lift)
    log_mean = labels.groupby("title_id")["log_share"].mean()

    tags = [set(g) | set(t) for g, t in zip(titles["genres"], titles["themes"])]
    sim = cfg.cosine_share * np.clip(emb @ emb.T, 0, None) + (1 - cfg.cosine_share) * _jaccard_matrix(tags)
    np.fill_diagonal(sim, -1.0)  # a title never informs itself
    region = _region_weights(state_ctx, states, cfg)

    out = []
    for i, t in enumerate(ids):
        for j, s in enumerate(states):
            if seen[i, j]:
                continue
            # content neighbours that observed state j
            cand = np.where(seen[:, j] & (sim[i] > 0))[0]
            cand = cand[np.argsort(-sim[i, cand])[:cfg.neighbours]]
            wc = sim[i, cand] ** cfg.sim_power
            n_c = _n_eff(wc)
            c_est = float((wc * lift[cand, j]).sum() / wc.sum()) if wc.sum() > 0 else 0.0
            # the title's own lift in related states
            wr = region[j] * seen[i]
            n_r = float(wr.sum())
            r_est = float((wr * np.nan_to_num(lift[i])).sum() / n_r) if n_r > 0 else 0.0
            if max(n_c, n_r) < cfg.min_support:
                continue
            est = (cfg.content_share * c_est * n_c / (n_c + cfg.content_prior)
                   + cfg.region_share * r_est * n_r / (n_r + cfg.region_prior))
            dlog = est + eff[j]
            log_share = dlog + float(log_mean.get(t, 0.0))
            out.append({"title_id": t, "state": s, "share": float(np.exp(log_share)), "log_share": log_share,
                        "dlog": dlog, "n_content": round(n_c, 2), "n_region": round(n_r, 2)})
    cols = ["title_id", "state", "share", "log_share", "dlog", "n_content", "n_region"]
    return pd.DataFrame(out, columns=cols)
