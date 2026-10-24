"""India success score: the architecture's Market Potential, built only from evidence we have.

    S = sum(w_i * c_i) / sum(w_i)   over the components that can be measured, each c_i on 0-100

50 always means "a typical anime in the training set". Components that cannot be measured for an
unreleased title (demand momentum, engagement) are reported as unavailable, never imputed, and the
weights of the rest are renormalised; `coverage` says how much of the 100% weight was measured.

Global popularity is the only outcome in csv/ and it is post-release. It is used here the way the
data dictionary allows: as a label for content-fit and comparables, never as a feature of the title.
"""
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm, spearmanr
from sklearn.linear_model import Ridge
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.preprocessing import StandardScaler

from app.ml import csv_data
from app.ml.comparables import ComparableIndex
from app.ml.scoring_config import MarketPotentialConfig
from app.ml.state_model import StateModel

ALPHAS = (1, 3, 10, 30, 100, 300, 1000)
INTERVAL_Z = 1.2816  # 80% two-sided normal
OUTCOMES_FILE = "titles_outcomes_global_POST_RELEASE.csv"
MIN_TITLES = 10
MIN_SKILL = 0.1  # a component must reach this held-out Spearman to count towards the score
BANDS = ((60.0, "above typical"), (40.0, "typical"), (0.0, "below typical"))
LABELS = {
    "content_fit": "Content fit", "demand_momentum": "Demand momentum",
    "regional_opportunity": "Regional opportunity", "engagement_quality": "Engagement quality",
    "comparable_performance": "Comparable performance",
}
UNAVAILABLE = {
    "demand_momentum": "no_pre_release_demand: an unreleased title has no Trends window before launch",
    "engagement_quality": "no_youtube_adapter: trailer engagement is not collected yet",
}
UNVALIDATED = "held-out Spearman {rho:.2f} is below {floor}: shown for information, excluded from the score"


def band(score: float) -> str:
    return next(name for floor, name in BANDS if score >= floor)


def _pct_of(value: float, reference: np.ndarray) -> float:
    """Mid-rank percentile (0-100) of `value` within `reference`."""
    ref = np.sort(reference)
    lo, hi = np.searchsorted(ref, value, "left"), np.searchsorted(ref, value, "right")
    return float(100 * (lo + hi) / 2 / len(ref))


@dataclass
class SuccessModel:
    """Content-fit ridge (target: global log popularity, a proxy) plus the pool's popularity percentiles."""
    ridge: Ridge
    scaler: StandardScaler
    columns: list[str]
    loo_pred: np.ndarray  # leave-one-franchise-out predictions for the pool
    pop_pct: pd.Series  # pool title_id -> popularity percentile 0-100
    resid_q80: float  # 80% absolute leave-one-franchise-out residual (log popularity)
    report: dict
    pool: pd.DataFrame  # titles with a global outcome (all csv/ titles, not only the state-labelled ones)
    pool_emb: np.ndarray
    config: MarketPotentialConfig = MarketPotentialConfig()

    @classmethod
    def from_csv(cls, model: StateModel, folder: Path) -> "SuccessModel | None":
        """None when the outcomes file is missing (the report then has no success score).

        Content fit and comparables need only a synopsis, a title and one global outcome, so they use every
        title in csv/ (300) rather than the 62 that also have state labels."""
        path = folder / OUTCOMES_FILE
        if not path.exists():
            return None
        outcomes = pd.read_csv(path, encoding="utf-8-sig")
        titles = csv_data.load(folder).titles
        usable = titles["title_id"].isin(outcomes["title_id"]) & titles["release_date"].notna()
        return cls.fit(model, outcomes, titles[usable].reset_index(drop=True)) if usable.sum() >= MIN_TITLES else None

    @classmethod
    def fit(cls, model: StateModel, outcomes: pd.DataFrame, titles: pd.DataFrame | None = None) -> "SuccessModel":
        """`outcomes`: title_id, log_popularity. `titles`: content frame to learn from (default: the state
        model's pool). Uses the state model's encoder, so the content features are the ones the state model sees."""
        pool = (model.pool if titles is None else titles).reset_index(drop=True)
        pop = outcomes.drop_duplicates("title_id").set_index("title_id")["log_popularity"]
        keep = pool["title_id"].isin(pop.index).to_numpy()
        pool = pool[keep].reset_index(drop=True)
        pool_emb = model.encoder.embed(pool)
        feats = model.encoder.transform(pool).drop(columns="title_id")
        y = pop.loc[pool["title_id"]].to_numpy(float)
        groups = pool["franchise_id"].to_numpy()
        if len(pool) < MIN_TITLES:
            raise ValueError("too few titles with outcomes to fit the content-fit model")

        best = None
        for alpha in ALPHAS:
            pred = np.zeros(len(y))
            for tr, te in LeaveOneGroupOut().split(feats, y, groups):
                sc = StandardScaler().fit(feats.iloc[tr])
                pred[te] = Ridge(alpha=alpha).fit(sc.transform(feats.iloc[tr]), y[tr]).predict(sc.transform(feats.iloc[te]))
            mse = float(np.mean((pred - y) ** 2))
            if best is None or mse < best[0]:
                best = (mse, alpha, pred)
        mse, alpha, loo = best
        scaler = StandardScaler().fit(feats)
        ridge = Ridge(alpha=alpha).fit(scaler.transform(feats), y)
        resid = np.sort(np.abs(y - loo))
        q80 = float(resid[min(len(resid), int(np.ceil((len(resid) + 1) * 0.8))) - 1])
        r2 = 1 - mse / float(np.var(y))
        rho = spearmanr(loo, y).statistic
        pop_pct = pd.Series([_pct_of(v, y) for v in y], index=pool["title_id"])
        full = pool
        index, found_pred, found_true = ComparableIndex(full, pool_emb), [], []
        for i, t in full.iterrows():
            rows = [(full.iloc[j]["title_id"], sim) for j, _, sim in index.find(t, pool_emb[i])
                    if full.iloc[j]["title_id"] in pop_pct.index]
            if len(rows) >= 2:
                w = np.array([max(sim, 1e-6) for _, sim in rows])
                found_pred.append(float((w * pop_pct.loc[[a for a, _ in rows]].to_numpy()).sum() / w.sum()))
                found_true.append(float(pop_pct[t["title_id"]]))
        cmp_rho = spearmanr(found_pred, found_true).statistic if len(found_pred) > 5 else float("nan")
        report = {"comparables_loo_spearman": 0.0 if np.isnan(cmp_rho) else float(cmp_rho),
                  "n_titles": len(pool), "alpha": alpha, "loo_r2": float(r2),
                  "loo_spearman": 0.0 if np.isnan(rho) else float(rho), "resid_q80_log_popularity": q80,
                  "validation": "leave-one-franchise-out (not time-ordered)",
                  "target": "global log popularity (post-release proxy; no India outcome exists in the data)"}
        return cls(ridge, scaler, list(feats.columns), loo, pop_pct, q80, report, pool, pool_emb)

    # ----------------------------------------------------------------- scoring
    def _content_fit(self, model: StateModel, frame: pd.DataFrame) -> dict:
        x = model.encoder.transform(frame).drop(columns="title_id")[self.columns]
        pred = float(self.ridge.predict(self.scaler.transform(x))[0])
        ref = self.loo_pred
        return {"value": _pct_of(pred, ref), "low": _pct_of(pred - self.resid_q80, ref),
                "high": _pct_of(pred + self.resid_q80, ref), "inputs": {"predicted_log_popularity": pred}}

    def _comparables(self, model: StateModel, frame: pd.DataFrame) -> dict | None:
        target = frame.iloc[0]
        found = ComparableIndex(self.pool, self.pool_emb).find(target, model.encoder.embed(frame)[0])
        rows = [(self.pool.iloc[i]["title_id"], sim) for i, _, sim in found
                if self.pool.iloc[i]["title_id"] in self.pop_pct.index]
        if not rows:
            return None
        w = np.array([max(s, 1e-6) for _, s in rows])
        v = self.pop_pct.loc[[t for t, _ in rows]].to_numpy()
        mean = float((w * v).sum() / w.sum())
        sd = float(np.sqrt((w * (v - mean) ** 2).sum() / w.sum()))
        half = INTERVAL_Z * sd / np.sqrt(len(rows))
        return {"value": mean, "low": max(0.0, mean - half), "high": min(100.0, mean + half),
                "inputs": {"n_comparables": len(rows), "weighted_sd": sd}}

    def score(self, model: StateModel, frame: pd.DataFrame, states: list[dict]) -> dict:
        """`states`: StateModel.predict()["states"] (lift, low, high, expected_share per state)."""
        cfg = self.config
        share = np.array([s["expected_share"] for s in states])
        sigma = model.y_scale
        z = {k: float((share * np.array([s[k] for s in states])).sum()) for k in ("lift", "low", "high")}
        regional = {"value": 100 * norm.cdf(z["lift"] / sigma), "low": 100 * norm.cdf(z["low"] / sigma),
                    "high": 100 * norm.cdf(z["high"] / sigma),
                    "inputs": {"share_weighted_lift": z["lift"], "lift_spread_sigma": sigma}}
        measured = {"content_fit": self._content_fit(model, frame), "regional_opportunity": regional,
                    "comparable_performance": self._comparables(model, frame)}

        skill = {"content_fit": self.report["loo_spearman"], "comparable_performance": self.report["comparables_loo_spearman"],
                 "regional_opportunity": model.report["metrics_oof"]["ensemble"]["spearman"]["mean"]}
        components, total = [], 0.0
        for key in LABELS:
            weight = getattr(cfg, key)
            m = measured.get(key)
            if m is None:
                components.append({"key": key, "label": LABELS[key], "weight": weight, "status": "unavailable",
                                   "reason": UNAVAILABLE.get(key, "no_comparable_titles"), "value": None,
                                   "low": None, "high": None, "inputs": {}})
                continue
            counted = skill[key] >= MIN_SKILL
            total += weight if counted else 0.0
            components.append({"key": key, "label": LABELS[key], "weight": weight,
                               "status": "ok" if counted else "unvalidated",
                               "reason": None if counted else UNVALIDATED.format(rho=skill[key], floor=MIN_SKILL),
                               "validation_spearman": round(float(skill[key]), 3),
                               "value": m["value"], "low": m["low"], "high": m["high"], "inputs": m["inputs"]})
        ok = [c for c in components if c["status"] == "ok"]
        if not ok:
            raise ValueError("no component passed validation; no success score can be computed")
        agg = {k: sum(c["weight"] * c[k] for c in ok) / total for k in ("value", "low", "high")}
        return {"config_version": cfg.version, "score": round(agg["value"], 1), "low": round(agg["low"], 1),
                "high": round(agg["high"], 1), "band": band(agg["value"]), "coverage": round(total, 2),
                "components": components,
                "meaning": "0-100 relative to the training titles: 50 is a typical anime, not a revenue forecast. "
                           "Confidence is a separate output.",
                "model": self.report}
