"""State-level model: predicts how a title's India demand splits across states and UTs.

Scope is deliberately narrow. Anything not about state-level demand (SEO, language, scoring of
other tasks) gets its own model package under models/<task>/, never this one.

Training uses every labelled title:
* the content encoder (vocabularies, TF-IDF, SVD, PCA) is fitted on ALL AniList titles, since it
  only reads content, never outcomes;
* comparables are drawn from every labelled title released earlier, in another franchise;
* honest evaluation, ensemble weights and conformal intervals come from out-of-fold predictions
  (expanding time windows, franchises kept apart), then the final models are refit on everything.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.ml import explain
from app.ml.comparables import ComparableIndex, comparable_features
from app.ml.confidence import title_confidence
from app.ml.evaluate import per_title_metrics, summarize
from app.ml.features import FEATURE_VERSION, ContentEncoder, build_rows, feature_columns
from app.ml.intervals import ConformalInterval
from app.ml.models import EnsembleModel, RidgeModel, StateMeanBaseline, XGBModel
from app.ml.scoring_config import ConfidenceConfig, as_dict
from app.ml.split import grouped_time_folds
from app.ml.states import STATES

TASK = "state"
NOMINAL_COVERAGE = 0.8
SMALL_TRAINING_SET = 100  # below this the model is exploratory
SPARSE_STATE_TITLES = 10  # states trained on fewer titles than this are flagged


def _folds(titles: pd.DataFrame, n_folds: int):
    """Expanding-window folds; training drops any title that shares a franchise with the validation block."""
    franchise = titles.set_index("title_id")["franchise_id"]
    for train_ids, val_ids in grouped_time_folds(titles, n_folds):
        blocked = set(franchise[list(val_ids)])
        yield {t for t in train_ids if franchise[t] not in blocked}, val_ids


@dataclass
class StateModel:
    encoder: ContentEncoder
    models: dict
    ensemble: EnsembleModel
    conformal: ConformalInterval
    cols: list[str]
    states: list[str]
    pool: pd.DataFrame  # labelled titles usable as comparables
    pool_emb: np.ndarray
    labels: pd.DataFrame  # title_id, state, share
    state_titles: dict[str, int]
    report: dict = field(default_factory=dict)
    version: str = ""

    task = TASK

    # ----------------------------------------------------------------- training
    @classmethod
    def train(cls, all_titles: pd.DataFrame, labels: pd.DataFrame, states: list[str],
              demand: pd.DataFrame | None = None, embedder=None, n_folds: int = 3) -> "StateModel":
        """`all_titles`: every AniList title (content only). `labels`: title_id, state, share."""
        labelled = (all_titles[all_titles["title_id"].isin(labels["title_id"].unique())]
                    .dropna(subset=["release_date"]).reset_index(drop=True))
        labels = labels[labels["title_id"].isin(labelled["title_id"]) & labels["state"].isin(states)]
        states = [s for s in states if s in set(labels["state"])]  # e.g. Ladakh has no Trends geo
        encoder = ContentEncoder(embedder).fit(all_titles)
        content, emb = encoder.transform(labelled), encoder.embed(labelled)
        index = ComparableIndex(labelled, emb)
        cmp_rows, _ = comparable_features(index, labelled, emb, labels, states)
        rows = build_rows(content, labels, states, demand=demand, comparable=cmp_rows)
        cols = feature_columns(rows)

        # Out-of-fold predictions: the only honest basis for metrics, blend weights and intervals.
        factories = (StateMeanBaseline, RidgeModel, XGBModel)
        oof = {f.name: [] for f in factories}
        oof_rows = []
        for train_ids, val_ids in _folds(labelled, n_folds):
            fit, val = rows[rows["title_id"].isin(train_ids)], rows[rows["title_id"].isin(val_ids)]
            if fit.empty or val.empty:
                continue
            for factory in factories:
                oof[factory.name].append(factory().fit(fit, cols).predict(val, cols))
            oof_rows.append(val)
        if not oof_rows:
            raise ValueError("too few labelled titles to build out-of-fold predictions")
        val_all = pd.concat(oof_rows)
        oof = {k: np.concatenate(v) for k, v in oof.items()}

        final = {f.name: f().fit(rows, cols) for f in factories}
        ensemble = EnsembleModel([final["ridge_genre_state"], final["xgboost"]])
        a, b = oof["ridge_genre_state"], oof["xgboost"]
        grid = np.linspace(0, 1, 11)
        y = val_all["share"].to_numpy()
        w = float(grid[int(np.argmin([np.sqrt(np.mean((g * a + (1 - g) * b - y) ** 2)) for g in grid]))])
        ensemble.weights = [w, 1 - w]
        oof_ens = w * a + (1 - w) * b
        conformal = ConformalInterval(1 - NOMINAL_COVERAGE).fit(y, oof_ens)

        metrics = {name: summarize(per_title_metrics(val_all, pred)) for name, pred in oof.items()}
        metrics["ensemble"] = summarize(per_title_metrics(val_all, oof_ens))
        contrib = explain.contributions(final["xgboost"], rows, cols)
        state_titles = labels.groupby("state")["title_id"].nunique().to_dict()
        report = {
            "task": TASK, "feature_version": FEATURE_VERSION, "embedder": encoder.embedder.name,
            "n_encoder_titles": len(all_titles), "n_labelled_titles": len(labelled),
            "n_rows": len(rows), "n_features": len(cols), "states": states, "n_folds": n_folds,
            "oof_titles": int(val_all["title_id"].nunique()),
            "evaluation": "out-of-fold, expanding time windows, franchise-separated; final models refit on all titles",
            "metrics_oof": metrics,
            "ensemble_weights": {"ridge": w, "xgboost": 1 - w},
            "intervals": {"nominal": NOMINAL_COVERAGE, "half_width": conformal.q_,
                          "oof_coverage": conformal.coverage(y, oof_ens)},
            "component_importance": explain.global_by_group(contrib),
            "titles_per_state": {s: int(state_titles.get(s, 0)) for s in states},
            "confidence_config": as_dict(ConfidenceConfig()),
            "exploratory": len(labelled) < SMALL_TRAINING_SET,
            "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        model = cls(encoder, final | {ensemble.name: ensemble}, ensemble, conformal, cols, states, labelled, emb,
                    labels[["title_id", "state", "share"]].reset_index(drop=True),
                    {s: int(state_titles.get(s, 0)) for s in states}, report)
        return model

    # --------------------------------------------------------------- prediction
    def predict(self, title: pd.DataFrame, demand: pd.DataFrame | None = None, top_drivers: int = 3) -> dict:
        """`title`: one row from features.titles_frame (release_date = planned or actual launch).
        `demand`: optional pre_* features per state; without it pre-release demand is zero."""
        if len(title) != 1 or pd.isna(title["release_date"].iloc[0]):
            raise ValueError("predict needs exactly one title with a release date")
        t = title.iloc[0]
        emb = self.encoder.embed(title)
        index = ComparableIndex(self.pool, self.pool_emb)
        found = index.find(t, emb[0])
        dummy = pd.DataFrame({"title_id": t["title_id"], "state": self.states, "share": np.nan})
        cmp_rows, cmp_stats = comparable_features(index, title, emb, self.labels, self.states)
        rows = build_rows(self.encoder.transform(title), dummy, self.states, demand=demand, comparable=cmp_rows)
        for c in self.cols:  # columns only present when demand data was used in training
            if c not in rows:
                rows[c] = 0.0
        pred = np.clip(self.ensemble.predict(rows, self.cols), 0, None)
        pred = pred / pred.sum() if pred.sum() > 0 else np.full(len(pred), 1 / len(pred))
        lo, hi = self.conformal.predict(pred)
        contrib = explain.contributions(self.models["xgboost"], rows, self.cols)

        pool_sims = self.pool_emb @ emb[0]
        other = (self.pool["franchise_id"] != t["franchise_id"]).to_numpy()
        ood = float(np.max(np.where(other, pool_sims, -np.inf))) if other.any() else 0.0
        conf = title_confidence(rows, pred, hi - lo, len(self.states), cmp_stats, {t["title_id"]: ood})
        order = (-pred).argsort().argsort() + 1
        n = len(self.states)
        results = []
        for i, state in enumerate(rows["state"]):
            row = contrib.iloc[i]
            drivers = [{"feature": f, "contribution": round(float(row[f]), 5)}
                       for f in row.abs().nlargest(top_drivers).index]
            results.append({"state": state, "name": STATES[state], "share": float(pred[i]),
                            "interest_index": float(pred[i] * n), "rank": int(order[i]),
                            "low": float(lo[i]), "high": float(hi[i]),
                            "train_titles": self.state_titles.get(state, 0), "drivers": drivers})
        results.sort(key=lambda r: r["rank"])
        factors = conf.iloc[0]
        comparables = [{"title_id": self.pool.iloc[i]["title_id"], "similarity": round(sim, 4)}
                       for i, _, sim in found]
        return {"model_version": self.version, "task": TASK, "states": results,
                "confidence": float(factors["confidence"]),
                "confidence_factors": {k: round(float(factors[k]), 4)
                                       for k in ("completeness", "comparables", "interval", "ood")},
                "comparables": comparables,
                "warnings": self._warnings(demand, len(found), ood)}

    def _warnings(self, demand, n_comparables: int, ood: float) -> list[str]:
        codes = []
        if demand is None or demand.empty:
            codes.append("no_pre_release_demand")
        if n_comparables < 3:
            codes.append("few_comparables")
        if ood < 0.3:
            codes.append("unlike_training_titles")
        if self.report.get("exploratory"):
            codes.append("small_training_set")
        if any(self.state_titles.get(s, 0) < SPARSE_STATE_TITLES for s in self.states):
            codes.append("sparse_state_training")
        return codes

    # -------------------------------------------------------------- persistence
    def save(self, root: Path = Path("models")) -> Path:
        """models/state/<version>/{model.joblib,report.json} and models/state/LATEST.json."""
        self.version = f"state-{FEATURE_VERSION}-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}"
        self.report["model_version"] = self.version
        folder = root / TASK / self.version
        folder.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, folder / "model.joblib")
        text = json.dumps(self.report, indent=2, default=str)
        (folder / "report.json").write_text(text, encoding="utf-8")
        (root / TASK / "LATEST.json").write_text(json.dumps({"version": self.version}), encoding="utf-8")
        return folder

    @staticmethod
    def load(root: Path = Path("models"), version: str | None = None) -> "StateModel":
        base = root / TASK
        if version is None:
            latest = base / "LATEST.json"
            if not latest.exists():
                raise FileNotFoundError(f"no trained state model under {base}")
            version = json.loads(latest.read_text(encoding="utf-8"))["version"]
        model = joblib.load(base / version / "model.joblib")
        if not isinstance(model, StateModel):
            raise TypeError(f"{base / version} is not a state model")
        return model

