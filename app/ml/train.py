"""Initial training run following the architecture's AI pipeline.

CONTENT DNA -> COMPARABLES -> FEATURES -> ENSEMBLE (baseline + XGBoost) -> EXPLAIN,
with conformal intervals and a separate confidence output. Evaluated once on a
time-based, franchise-grouped held-out set.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from app.ml import explain
from app.ml.comparables import ComparableIndex, comparable_features
from app.ml.confidence import title_confidence
from app.ml.evaluate import per_title_metrics, summarize
from app.ml.features import (
    FEATURE_VERSION,
    ContentEncoder,
    build_rows,
    feature_columns,
    group_columns,
)
from app.ml.intervals import ConformalInterval
from app.ml.models import EnsembleModel, RidgeModel, StateMeanBaseline, XGBModel
from app.ml.scoring_config import ConfidenceConfig, MarketPotentialConfig, as_dict
from app.ml.split import franchise_time_split

NOMINAL_COVERAGE = 0.8
ABLATIONS = {
    "content": ("content", "regional"),
    "demand": ("demand", "regional"),
    "comparable": ("comparable", "regional"),
    "all": ("content", "demand", "regional", "comparable"),
}


def run(
    titles: pd.DataFrame,
    labels: pd.DataFrame,
    states: list[str],
    state_context: pd.DataFrame | None = None,
    demand: pd.DataFrame | None = None,
    test_frac: float = 0.2,
    calib_frac: float = 0.2,
    embedder=None,
) -> tuple[dict, dict, ContentEncoder]:
    """`titles` from features.titles_frame; `labels` has title_id, state, share."""
    titles = (
        titles[titles["title_id"].isin(labels["title_id"].unique())]
        .dropna(subset=["release_date"])
        .reset_index(drop=True)
    )
    train_ids, test_ids = franchise_time_split(titles, test_frac)
    fit_ids, calib_ids = franchise_time_split(
        titles[titles["title_id"].isin(train_ids)], calib_frac
    )

    first = titles.groupby("franchise_id")["release_date"].min()
    by_title = titles.set_index("title_id")
    assert (
        first[by_title.loc[list(train_ids), "franchise_id"]].max()
        <= first[by_title.loc[list(test_ids), "franchise_id"]].min()
    ), "test franchises must be newer"

    # Content DNA is fitted on the fitting titles only; comparables come from the training side only.
    encoder = ContentEncoder(embedder).fit(titles[titles["title_id"].isin(fit_ids)])
    content = encoder.transform(titles)
    emb = encoder.embed(titles)
    pool_mask = titles["title_id"].isin(train_ids).to_numpy()
    index = ComparableIndex(titles[pool_mask], emb[pool_mask])
    cmp_rows, cmp_stats = comparable_features(index, titles, emb, labels, states)

    rows = build_rows(content, labels, states, state_context, demand, cmp_rows)
    cols = feature_columns(rows)
    fit, calib, test = (rows[rows["title_id"].isin(ids)] for ids in (fit_ids, calib_ids, test_ids))

    models = {}
    for model in (StateMeanBaseline(), RidgeModel(), XGBModel()):
        models[model.name] = model.fit(fit, cols)
    ensemble = EnsembleModel([models["ridge_genre_state"], models["xgboost"]]).fit_weights(
        calib, cols
    )
    models[ensemble.name] = ensemble
    results = {
        name: summarize(per_title_metrics(test, m.predict(test, cols)))
        for name, m in models.items()
    }

    # Intervals: coverage on unseen titles vs the nominal level is the calibration error.
    ens_calib, ens_test = ensemble.predict(calib, cols), ensemble.predict(test, cols)
    conformal = ConformalInterval(1 - NOMINAL_COVERAGE).fit(calib["share"].to_numpy(), ens_calib)
    coverage = conformal.coverage(test["share"].to_numpy(), ens_test)
    lo, hi = conformal.predict(ens_test)

    # Which model component carries the signal (content / demand / regional / comparable).
    ablation = {}
    for label, groups in ABLATIONS.items():
        gcols = group_columns(cols, *groups)
        if any(not c.startswith("state_") for c in gcols):
            m = XGBModel().fit(fit, gcols)
            ablation[label] = summarize(per_title_metrics(test, m.predict(test, gcols)))[
                "top3_hit"
            ]["mean"]

    # Confidence is a separate output, then checked against actual per-title accuracy.
    pool_titles = titles[pool_mask]
    same_franchise = (
        titles["franchise_id"].to_numpy()[:, None]
        == pool_titles["franchise_id"].to_numpy()[None, :]
    )
    max_sim = dict(
        zip(
            titles["title_id"],
            np.where(same_franchise, -np.inf, emb @ emb[pool_mask].T).max(axis=1),
            strict=True,
        )
    )
    conf = title_confidence(test, ens_test, hi - lo, len(states), cmp_stats, max_sim)
    per_title = per_title_metrics(test, ens_test).merge(conf, on="title_id")
    conf_corr = (
        spearmanr(per_title["confidence"], per_title["top3_hit"]).statistic
        if len(per_title) > 2 and per_title["top3_hit"].nunique() > 1
        else None
    )

    contrib = explain.contributions(models["xgboost"], test, cols)
    example = test.index[0]
    report = {
        "feature_version": FEATURE_VERSION,
        "embedder": encoder.embedder.name,
        "n_train_titles": len(train_ids),
        "n_test_titles": len(test_ids),
        "n_fit_titles": len(fit_ids),
        "n_calibration_titles": len(calib_ids),
        "n_features": len(cols),
        "states": states,
        "test_release_from": str(by_title.loc[list(test_ids), "release_date"].min().date()),
        "metrics": results,
        "beats_baselines": results["xgboost"]["top3_hit"]["mean"]
        > max(
            results["state_mean"]["top3_hit"]["mean"],
            results["ridge_genre_state"]["top3_hit"]["mean"],
        ),
        "ensemble_weights": {"ridge": ensemble.weights[0], "xgboost": ensemble.weights[1]},
        "intervals": {
            "nominal": NOMINAL_COVERAGE,
            "observed": coverage,
            "calibration_error": abs(coverage - NOMINAL_COVERAGE),
            "half_width": conformal.q_,
        },
        "ablation_top3_hit": ablation,
        "component_importance": explain.global_by_group(contrib),
        "confidence": {
            "mean": float(conf["confidence"].mean()),
            "spearman_with_top3_hit": (
                None if conf_corr is None or np.isnan(conf_corr) else float(conf_corr)
            ),
        },
        "example_explanation": {
            "title_id": test.loc[example, "title_id"],
            "state": test.loc[example, "state"],
            "top_features": explain.local(contrib, example),
        },
        "scoring_config": as_dict(MarketPotentialConfig()),
        "confidence_config": as_dict(ConfidenceConfig()),
        "engagement_quality": "unavailable: YouTube not collected; weight reported, not imputed",
    }
    objects = {
        "encoder": encoder,
        "models": models,
        "conformal": conformal,
        "cols": cols,
        "states": states,
    }
    return report, objects, encoder


def save(report: dict, out: Path, objects: dict | None = None) -> Path:
    """Write a versioned model directory plus the latest report."""
    version = f"{report['feature_version']}-{datetime.now(UTC):%Y%m%dT%H%M%S}"
    folder = out / version
    folder.mkdir(parents=True, exist_ok=True)
    report = {**report, "model_version": version}
    text = json.dumps(report, indent=2, default=str)
    (folder / "report.json").write_text(text, encoding="utf-8")
    (out / "initial_report.json").write_text(text, encoding="utf-8")
    if objects:
        joblib.dump(objects, folder / "model.joblib")
    return folder
