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
from app.ml.synthetic import SyntheticConfig, synthesize
from app.ml.synthetic import as_dict as synthetic_as_dict
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


SPARSE_GROUP = 20  # states with fewer real training titles than this form the "sparse" group in diagnostics


def _state_error(val: pd.DataFrame, pred: np.ndarray, y: np.ndarray, state_titles: dict) -> dict:
    """Held-out lift error per state group. Bias = mean(pred - y) per state, averaged in absolute value."""
    df = pd.DataFrame({"state": val["state"].to_numpy(), "err": pred - y})
    per = df.groupby("state")["err"].agg(bias="mean", rmse=lambda e: float(np.sqrt(np.mean(e ** 2))), n="size")
    sparse = np.array([state_titles.get(s, 0) < SPARSE_GROUP for s in per.index])
    out = {}
    for name, mask in (("sparse", sparse), ("dense", ~sparse)):
        g = per[mask]
        out[name] = {"states": int(len(g)), "mean_abs_bias": float(g["bias"].abs().mean()) if len(g) else None,
                     "rmse": float(np.sqrt(np.average(g["rmse"] ** 2, weights=g["n"]))) if len(g) else None}
    out["per_state"] = {s: {"bias": float(r.bias), "rmse": float(r.rmse), "n": int(r.n)} for s, r in per.iterrows()}
    return out


def _input_completeness(t: pd.Series) -> float:
    """0-1: how much of the title's own description was supplied (themes, studio, length, synopsis)."""
    def present(col):
        return float(col in t and pd.notna(t[col]) and t[col] not in ("", 0))
    themes = min(len(t["themes"]) / 3, 1.0) if "themes" in t and t["themes"] is not None else 0.0
    synopsis = min(len(str(t.get("synopsis") or "")) / 300, 1.0)
    return float(np.mean([themes, present("studio"), present("episodes"), present("minutes"), synopsis]))


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
    state_synthetic: dict[str, int] = field(default_factory=dict)  # synthetic training rows per state

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
              embedder=None, n_folds: int = 3, min_theme_titles: int = 10,
              synthetic: SyntheticConfig | None = SyntheticConfig()) -> "StateModel":
        """`all_titles`: content frame of every known title. `labels`: title_id, state, share.

        `synthetic`: fill the title x state cells Trends left empty (see app/ml/synthetic.py) and train on them
        at a reduced weight. Validation always uses real rows only, and the report compares the model with
        and without the synthetic rows on identical folds. None trains on real rows only.
        """
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
        rows = rows.assign(w=1.0, is_synthetic=0)
        cols = feature_columns(rows)
        ctx = state_ctx if state_ctx is not None else pd.DataFrame({"state": states})
        label_cols = ["title_id", "state", "share", "log_share", "dlog"]

        def synthetic_rows(ids: set, eff: pd.Series) -> pd.DataFrame:
            """Synthetic rows built from the labels of `ids` only (never from validation titles)."""
            if synthetic is None:
                return rows.iloc[0:0]
            keep = labelled["title_id"].isin(ids).to_numpy()
            sub, sub_emb = labelled[keep].reset_index(drop=True), emb[keep]
            syn = synthesize(labels[labels["title_id"].isin(ids)], sub, sub_emb, states, ctx, eff, synthetic)
            if syn.empty:
                return rows.iloc[0:0]
            built, _ = cls._rows(encoder, sub, sub_emb, syn[label_cols], states, demand, state_ctx,
                                 labelled, emb, labels)
            return built.assign(w=synthetic.weight, is_synthetic=1)

        # Out-of-fold predictions: the only honest basis for metrics, blend weights and intervals.
        factories = (lambda: StateMeanBaseline(TARGET), lambda: RidgeModel(target=TARGET),
                     lambda: XGBModel(target=TARGET))
        names = [f().name for f in factories]
        variants = ["real_only"] + (["augmented"] if synthetic is not None else [])
        oof = {v: {n: [] for n in names} for v in variants}
        parts = []
        for train_ids, val_ids in _folds(labelled, n_folds):
            sub = labels[labels["title_id"].isin(train_ids)]
            if sub.empty:
                continue
            eff = state_effect(sub)  # means from this fold's training titles only
            real_fit = add_lift(rows[rows["title_id"].isin(train_ids)], eff)
            val = add_lift(rows[rows["title_id"].isin(val_ids)], eff)
            if real_fit.empty or val.empty:
                continue
            syn_fit = add_lift(synthetic_rows(train_ids, eff), eff)
            for v in variants:
                fit = pd.concat([real_fit, syn_fit], ignore_index=True) if v == "augmented" else real_fit
                for name, factory in zip(names, factories):
                    oof[v][name].append(factory().fit(fit, cols).predict(val, cols))
            parts.append(val)
        if not parts:
            raise ValueError("too few labelled titles to build out-of-fold predictions")
        val_all = pd.concat(parts)
        oof = {v: {k: np.concatenate(p) for k, p in d.items()} for v, d in oof.items()}
        y = val_all[TARGET].to_numpy()
        state_titles = labels.groupby("state")["title_id"].nunique().to_dict()

        def blend(o: dict) -> tuple[float, np.ndarray]:
            a, b = o["ridge_genre_state"], o["xgboost"]
            grid = np.linspace(0, 1, 11)  # blend weight chosen for ranking quality, the product's use
            quality = [per_title_metrics(val_all, g * a + (1 - g) * b, target=TARGET)["spearman"].mean() for g in grid]
            w = float(grid[int(np.nanargmax(quality))])
            return w, w * a + (1 - w) * b

        blends = {v: blend(oof[v]) for v in variants}
        by_variant, state_errors = {}, {}
        for v in variants:
            m = {n: summarize(per_title_metrics(val_all, p, target=TARGET)) for n, p in oof[v].items()}
            m["ensemble"] = summarize(per_title_metrics(val_all, blends[v][1], target=TARGET))
            by_variant[v] = m
            state_errors[v] = _state_error(val_all, blends[v][1], y, state_titles)
        main = variants[-1]  # augmented when enabled
        w, oof_ens = blends[main]
        metrics = by_variant[main]
        conformal = ConformalInterval(1 - NOMINAL_COVERAGE, floor_at_zero=False).fit(y, oof_ens)

        effect = state_effect(labels)
        full = add_lift(rows, effect)
        syn_full = add_lift(synthetic_rows(set(labelled["title_id"]), effect), effect)
        fit_all = pd.concat([full, syn_full], ignore_index=True) if main == "augmented" else full
        final = {f().name: f().fit(fit_all, cols) for f in factories}
        ensemble = EnsembleModel([final["ridge_genre_state"], final["xgboost"]])
        ensemble.weights = [w, 1 - w]

        sizes = val_all.groupby("title_id").size()
        contrib = explain.contributions(final["xgboost"], full, cols)
        state_synth = syn_full.groupby("state").size().to_dict() if len(syn_full) else {}
        report = {
            "task": TASK,
            "target": "lift = log_share - title mean - state mean + grand mean (means from training titles only)",
            "feature_version": FEATURE_VERSION, "embedder": encoder.embedder.name,
            "n_encoder_titles": len(all_titles), "n_labelled_titles": len(labelled),
            "n_rows": len(rows), "n_synthetic_rows": len(syn_full) if main == "augmented" else 0,
            "n_features": len(cols), "states": states, "n_folds": n_folds,
            "oof_titles": int(val_all["title_id"].nunique()), "chance_top3_hit": float(np.mean(3 / sizes)),
            "evaluation": "out-of-fold, expanding time windows, franchise-separated, real rows only; "
                          "final models refit on all titles",
            "metrics_oof": metrics,
            "state_error_oof": state_errors[main],
            "ensemble_weights": {"ridge": w, "xgboost": 1 - w},
            "intervals": {"nominal": NOMINAL_COVERAGE, "half_width_lift": conformal.q_,
                          "oof_coverage": conformal.coverage(y, oof_ens)},
            "component_importance": explain.global_by_group(contrib),
            "titles_per_state": {s: int(state_titles.get(s, 0)) for s in states},
            "synthetic_rows_per_state": {s: int(state_synth.get(s, 0)) for s in states},
            "synthetic": None if synthetic is None else {
                "config": synthetic_as_dict(synthetic), "used_in_final_model": main == "augmented",
                "comparison_oof": {v: {**by_variant[v], "state_error": state_errors[v]} for v in variants},
                "note": "Same folds, same real validation rows; synthetic rows are built from training titles only "
                        "and only change the training set."},
            "confidence_config": as_dict(ConfidenceConfig()),
            "exploratory": len(labelled) < SMALL_TRAINING_SET,
            "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        return cls(encoder, final | {ensemble.name: ensemble}, ensemble, conformal, cols, states, labelled, emb,
                   labels, effect, state_ctx, float(np.std(y)),
                   {s: int(state_titles.get(s, 0)) for s in states}, report,
                   state_synthetic={s: int(state_synth.get(s, 0)) for s in states})

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
        ridge, boost = (m.predict(rows, self.cols) for m in self.ensemble.members[:2])
        has_history = float(bool(rows["parent_n"].max() or rows["studio_n"].max()))
        conf = title_confidence(rows, lift, hi - lo, len(self.states), stats, {t["title_id"]: ood},
                                scale=self.y_scale, inputs=_input_completeness(t), history=has_history,
                                disagreement=ridge - boost)
        order = (-lift).argsort().argsort() + 1
        results = []
        for i, state in enumerate(rows["state"]):
            row = contrib.iloc[i]
            results.append({"state": state, "name": STATES[state], "lift": float(lift[i]), "rank": int(order[i]),
                            "low": float(lo[i]), "high": float(hi[i]), "expected_share": float(share[i]),
                            "train_titles": self.state_titles.get(state, 0),
                            "synthetic_rows": getattr(self, "state_synthetic", {}).get(state, 0),
                            "drivers": [{"feature": f, "contribution": round(float(row[f]), 5)}
                                        for f in row.abs().nlargest(top_drivers).index]})
        results.sort(key=lambda r: r["rank"])
        f = conf.iloc[0]
        names = self.pool["name_en"] if "name_en" in self.pool else None
        comparables = [{"title_id": self.pool.iloc[i]["title_id"], "similarity": round(float(masked[i]), 4),
                        **({"name": names.iloc[i]} if names is not None else {})}
                       for i in np.argsort(-masked)[:5] if np.isfinite(masked[i])]
        history = {k: int(rows[k].max()) for k in ("parent_n", "studio_n")}
        return {"model_version": self.version, "task": TASK, "states": results,
                "confidence": float(f["confidence"]),
                "confidence_factors": {k: round(float(f[k]), 4)
                                       for k in ("completeness", "comparables", "agreement", "interval", "ood")},
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
        if self.report.get("n_synthetic_rows"):
            codes.append("synthetic_augmented")
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
