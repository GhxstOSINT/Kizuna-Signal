"""Initial training run: baselines vs constrained XGBoost, time-split, evaluated once on the test set."""
import json
from pathlib import Path

import pandas as pd

from app.ml.evaluate import per_title_metrics, summarize
from app.ml.features import FEATURE_VERSION, ContentEncoder, build_rows, feature_columns
from app.ml.models import RidgeModel, StateMeanBaseline, XGBModel
from app.ml.split import time_split


def run(titles: pd.DataFrame, labels: pd.DataFrame, states: list[str],
        state_context: pd.DataFrame | None = None,
        demand: pd.DataFrame | None = None, test_frac: float = 0.2) -> tuple[dict, dict, ContentEncoder]:
    """`titles` from features.titles_frame; `labels` has title_id, state, share."""
    titles = titles[titles["title_id"].isin(labels["title_id"].unique())].dropna(subset=["release_date"])
    train_ids, test_ids = time_split(titles, test_frac)

    # Check ordering: every training title is released no later than every test title.
    dates = titles.set_index("title_id")["release_date"]
    assert dates[list(train_ids)].max() <= dates[list(test_ids)].min()

    encoder = ContentEncoder().fit(titles[titles["title_id"].isin(train_ids)])
    content = encoder.transform(titles)
    rows = build_rows(content, labels, states, state_context, demand)
    cols = feature_columns(rows)
    train, test = rows[rows["title_id"].isin(train_ids)], rows[rows["title_id"].isin(test_ids)]

    results, fitted = {}, {}
    for model in (StateMeanBaseline(), RidgeModel(), XGBModel()):
        model.fit(train, cols)
        fitted[model.name] = model
        results[model.name] = summarize(per_title_metrics(test, model.predict(test, cols)))

    return {
        "feature_version": FEATURE_VERSION,
        "n_train_titles": len(train_ids), "n_test_titles": len(test_ids),
        "n_features": len(cols), "states": states,
        "test_release_from": str(dates[list(test_ids)].min().date()),
        "metrics": results,
        "beats_baselines": results["xgboost"]["top3_hit"]["mean"]
        > max(results["state_mean"]["top3_hit"]["mean"], results["ridge_genre_state"]["top3_hit"]["mean"]),
    }, fitted, encoder


def save(report: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "initial_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
