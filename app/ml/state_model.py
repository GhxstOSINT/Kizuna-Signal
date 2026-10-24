"""State-level model: predicts where a title over-performs across Indian states and UTs.

Scope is deliberately narrow. Anything not about state-level demand (SEO, language, other scoring
tasks) gets its own model package under models/<task>/, never this one.

Target: `lift` (see state_features) - how far a title's share in a state sits above what a typical
anime gets there. Raw share is dominated by each state's baseline and is not trained on.

Training uses every labelled title:
* the content encoder is fitted on ALL titles in the source tables (it only reads content);
* history features use only titles whose label window ended before the title launched;
* metrics, blend weight and intervals come from out-of-fold predictions (expanding time windows,
  franchises kept apart in training, state/grand means recomputed from each fold's training titles),
  then the final models are refit on everything.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.ml import explain
from app.ml.confidence import title_confidence
from app.ml.evaluate import per_title_metrics, summarize
from app.ml.features import FEATURE_VERSION, ContentEncoder, build_rows, feature_columns
from app.ml.intervals import ConformalInterval
from app.ml.models import EnsembleModel, RidgeModel, StateMeanBaseline, XGBModel
from app.ml.scoring_config import ConfidenceConfig, as_dict
from app.ml.split import grouped_time_folds
from app.ml.state_features import add_lift, history_features, state_effect, title_extras, with_dlog
from app.ml.states import STATES

TASK = "state"
TARGET = "y"
NOMINAL_COVERAGE = 0.8
SMALL_TRAINING_SET = 100  # below this the model is exploratory
SPARSE_STATE_TITLES = 10  # states trained on fewer titles than this are flagged
HISTORY_FILL = ("cmp_dlog", "parent_dlog", "studio_dlog", "cmp_n", "parent_n", "studio_n")


def _folds(titles: pd.DataFrame, n_folds: int):
    """Expanding-window folds; training drops any title that shares a franchise with the validation block."""
    franchise = titles.set_index("title_id")["franchise_id"]
    for train_ids, val_ids in grouped_time_folds(titles, n_folds):
        blocked = set(franchise[list(val_ids)])
        yield {t for t in train_ids if franchise[t] not in blocked}, val_ids


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max())
    return e / e.sum()


@dataclass
class StateModel:
    encoder: ContentEncoder
    models: dict
    ensemble: EnsembleModel
    conformal: ConformalInterval
    cols: list[str]
    states: list[str]
    pool: pd.DataFrame  # labelled titles usable as history
    pool_emb: np.ndarray
    labels: pd.DataFrame  # title_id, state, share, log_share, dlog
    effect: pd.Series  # state effect (state mean log share - grand mean), all training titles
    state_ctx: pd.DataFrame | None
    y_scale: float  # spread of out-of-fold lift, the yardstick for interval width
    state_titles: dict[str, int]
    report: dict = field(default_factory=dict)
    version: str = ""

    task = TASK

    # ---------------------------------------------------------------- features
    @staticmethod
    def _rows(encoder, titles, emb, labels, states, demand, state_ctx, pool, pool_emb, hist_labels):
        content = encoder.transform(titles).merge(title_extras(titles), on="title_id")
        rows = build_rows(content, labels, states, state_ctx, demand)
        hist, stats = history_features(titles, emb, pool, pool_emb, hist_labels, states)
        rows = rows.merge(hist, on=["title_id", "state"], how="left")
        rows[list(HISTORY_FILL)] = rows[list(HISTORY_FILL)].fillna(0.0)
        return rows, stats

    # ----------------------------------------------------------------- training
    @classmethod
    def train(cls, all_titles: pd.DataFrame, labels: pd.DataFrame, states: list[str],
              demand: pd.DataFrame | None = None, state_ctx: pd.DataFrame | None = None,
              embedder=None, n_folds: int = 3, min_theme_titles: int = 10) -> "StateModel":
        """`all_titles`: content frame of every known title. `labels`: title_id, state, share."""
        labelled = (all_titles[all_titles["title_id"].isin(labels["title_id"].unique())]
                    .dropna(subset=["release_date"]).reset_index(drop=True))
        labels = labels[labels["title_id"].isin(labelled["title_id"]) & labels["state"].isin(states)]
        states = [s for s in states if s in set(labels["state"])]  # e.g. Ladakh has no Trends geo
        labels = with_dlog(labels).reset_index(drop=True)
        if state_ctx is not None:
            state_ctx = state_ctx[state_ctx["state"].isin(states)].reset_index(drop=True)

        encoder = ContentEncoder(embedder, max_themes=300, min_theme_titles=min_theme_titles).fit(all_titles)
        emb = encoder.embed(labelled)
        rows, _ = cls._rows(encoder, labelled, emb, labels, states, demand, state_ctx, labelled, emb, labels)
        cols = feature_columns(rows)

        # Out-of-fold predictions: the only honest basis for metrics, blend weights and intervals.
        factories = (lambda: StateMeanBaseline(TARGET), lambda: RidgeModel(target=TARGET),
                     lambda: XGBModel(target=TARGET))
        names = [f().name for f in factories]
        oof = {n: [] for n in names}
        parts = []
        for train_ids, val_ids in _folds(labelled, n_folds):
            sub = labels[labels["title_id"].isin(train_ids)]
            if sub.empty:
                continue
            eff = state_effect(sub)  # means from this fold's training titles only
            fit = add_lift(rows[rows["title_id"].isin(train_ids)], eff)
            val = add_lift(rows[rows["title_id"].isin(val_ids)], eff)
            if fit.empty or val.empty:
                continue
            for name, factory in zip(names, factories):
                oof[name].append(factory().fit(fit, cols).predict(val, cols))
            parts.append(val)
        if not parts:
            raise ValueError("too few labelled titles to build out-of-fold predictions")
        val_all = pd.concat(parts)
        oof = {k: np.concatenate(v) for k, v in oof.items()}

        effect = state_effect(labels)
        full = add_lift(rows, effect)
        final = {f().name: f().fit(full, cols) for f in factories}
        ensemble = EnsembleModel([final["ridge_genre_state"], final["xgboost"]])
        a, b = oof["ridge_genre_state"], oof["xgboost"]
        grid = np.linspace(0, 1, 11)  # blend weight chosen for ranking quality, the product's use
        rank_quality = [per_title_metrics(val_all, g * a + (1 - g) * b, target=TARGET)["spearman"].mean() for g in grid]
        w = float(grid[int(np.nanargmax(rank_quality))])
        ensemble.weights = [w, 1 - w]
        oof_ens = w * a + (1 - w) * b
        y = val_all[TARGET].to_numpy()
        conformal = ConformalInterval(1 - NOMINAL_COVERAGE, floor_at_zero=False).fit(y, oof_ens)

        metrics = {n: summarize(per_title_metrics(val_all, p, target=TARGET)) for n, p in oof.items()}
        metrics["ensemble"] = summarize(per_title_metrics(val_all, oof_ens, target=TARGET))
        sizes = val_all.groupby("title_id").size()
        contrib = explain.contributions(final["xgboost"], full, cols)
        state_titles = labels.groupby("state")["title_id"].nunique().to_dict()
        report = {
            "task": TASK,
            "target": "lift = log_share - title mean - state mean + grand mean (means from training titles only)",
            "feature_version": FEATURE_VERSION, "embedder": encoder.embedder.name,
            "n_encoder_titles": len(all_titles), "n_labelled_titles": len(labelled),
            "n_rows": len(rows), "n_features": len(cols), "states": states, "n_folds": n_folds,
            "oof_titles": int(val_all["title_id"].nunique()), "chance_top3_hit": float(np.mean(3 / sizes)),
            "evaluation": "out-of-fold, expanding time windows, franchise-separated; final models refit on all titles",
            "metrics_oof": metrics,
            "ensemble_weights": {"ridge": w, "xgboost": 1 - w},
            "intervals": {"nominal": NOMINAL_COVERAGE, "half_width_lift": conformal.q_,
                          "oof_coverage": conformal.coverage(y, oof_ens)},
            "component_importance": explain.global_by_group(contrib),
            "titles_per_state": {s: int(state_titles.get(s, 0)) for s in states},
            "confidence_config": as_dict(ConfidenceConfig()),
            "exploratory": len(labelled) < SMALL_TRAINING_SET,
            "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        return cls(encoder, final | {ensemble.name: ensemble}, ensemble, conformal, cols, states, labelled, emb,
                   labels, effect, state_ctx, float(np.std(y)),
                   {s: int(state_titles.get(s, 0)) for s in states}, report)

    # --------------------------------------------------------------- prediction
    def predict(self, title: pd.DataFrame, demand: pd.DataFrame | None = None, top_drivers: int = 3) -> dict:
        """`title`: one content-frame row (release_date = planned or actual launch).
        `demand`: optional pre_* features per state; without it pre-release demand is zero."""
        if len(title) != 1 or pd.isna(title["release_date"].iloc[0]):
            raise ValueError("predict needs exactly one title with a release date")
        t = title.iloc[0]
        emb = self.encoder.embed(title)
        dummy = pd.DataFrame({"title_id": t["title_id"], "state": self.states, "share": np.nan})
        rows, stats = self._rows(self.encoder, title, emb, dummy, self.states, demand, self.state_ctx,
                                 self.pool, self.pool_emb, self.labels)
        for c in self.cols:  # columns only present when demand data was used in training
            if c not in rows:
                rows[c] = 0.0
        lift = self.ensemble.predict(rows, self.cols)
        lo, hi = self.conformal.predict(lift)
        share = _softmax(rows["state"].map(self.effect).fillna(0.0).to_numpy() + lift)
        contrib = explain.contributions(self.models["xgboost"], rows, self.cols)

        sims = self.pool_emb @ emb[0]
        older_other = ((self.pool["franchise_id"] != t["franchise_id"])
                       & (self.pool["release_date"] < t["release_date"])).to_numpy()
        masked = np.where(older_other, sims, -np.inf)
        ood = float(masked.max()) if older_other.any() else 0.0
        conf = title_confidence(rows, lift, hi - lo, len(self.states), stats, {t["title_id"]: ood},
                                scale=self.y_scale)
        order = (-lift).argsort().argsort() + 1
        results = []
        for i, state in enumerate(rows["state"]):
            row = contrib.iloc[i]
            results.append({"state": state, "name": STATES[state], "lift": float(lift[i]), "rank": int(order[i]),
                            "low": float(lo[i]), "high": float(hi[i]), "expected_share": float(share[i]),
                            "train_titles": self.state_titles.get(state, 0),
                            "drivers": [{"feature": f, "contribution": round(float(row[f]), 5)}
                                        for f in row.abs().nlargest(top_drivers).index]})
        results.sort(key=lambda r: r["rank"])
        f = conf.iloc[0]
        comparables = [{"title_id": self.pool.iloc[i]["title_id"], "similarity": round(float(masked[i]), 4)}
                       for i in np.argsort(-masked)[:5] if np.isfinite(masked[i])]
        history = {k: int(rows[k].max()) for k in ("parent_n", "studio_n")}
        return {"model_version": self.version, "task": TASK, "states": results,
                "confidence": float(f["confidence"]),
                "confidence_factors": {k: round(float(f[k]), 4)
                                       for k in ("completeness", "comparables", "interval", "ood")},
                "comparables": comparables, "history_titles": history,
                "warnings": self._warnings(demand, len(comparables), ood, history)}

    def _warnings(self, demand, n_comparables: int, ood: float, history: dict) -> list[str]:
        codes = []
        if demand is None or demand.empty:
            codes.append("no_pre_release_demand")
        if n_comparables < 3:
            codes.append("few_comparables")
        if ood < 0.3:
            codes.append("unlike_training_titles")
        if not history["parent_n"]:
            codes.append("no_franchise_history")
        if self.report.get("exploratory"):
            codes.append("small_training_set")
        if any(self.state_titles.get(s, 0) < SPARSE_STATE_TITLES for s in self.states):
            codes.append("sparse_state_training")
        return codes

    # -------------------------------------------------------------- persistence
    def save(self, root: Path = Path("models")) -> Path:
        """models/state/<version>/{model.joblib,report.json} and models/state/LATEST.json."""
        self.version = f"state-lift-{FEATURE_VERSION}-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}"
        self.report["model_version"] = self.version
        folder = root / TASK / self.version
        folder.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, folder / "model.joblib")
        (folder / "report.json").write_text(json.dumps(self.report, indent=2, default=str), encoding="utf-8")
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
