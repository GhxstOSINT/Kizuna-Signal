"""State model. Training data is SYNTHETIC, so these prove plumbing and invariants
(no leakage, stable output shape), not predictive quality."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from app.ml.features import titles_frame
from app.ml.schema import TitleRecord
from app.ml.state_model import StateModel
from app.ml.states import PILOT_STATES, STATES
from app.services.state_frame import make_frame
from tests.support.ml_data import synthetic


@pytest.fixture(scope="module")
def model():
    records, labels = synthetic(60)
    return StateModel.train(titles_frame(records), labels, PILOT_STATES, min_theme_titles=1)


def new_title(release=date(2030, 1, 1), genre="Action"):
    return titles_frame(
        [
            TitleRecord(
                title_id="new",
                franchise_id="new",
                genres=[genre],
                themes=[genre.lower()],
                format="TV",
                original_release_date=release,
                synopsis="sword battle war hero story adventure",
            )
        ]
    )


def test_report_describes_out_of_fold_evaluation_and_small_data(model):
    r = model.report
    assert r["task"] == "state" and r["n_labelled_titles"] == 60 and r["oof_titles"] < 60
    assert r["target"].startswith("lift") and 0 < r["chance_top3_hit"] < 1
    assert set(r["metrics_oof"]) == {"state_mean", "ridge_genre_state", "xgboost", "ensemble"}
    assert r["exploratory"] is True and r["ensemble_weights"]["ridge"] + r["ensemble_weights"][
        "xgboost"
    ] == pytest.approx(1)
    assert sum(r["titles_per_state"].values()) == 60 * len(PILOT_STATES)


def test_prediction_shape_and_invariants(model):
    out = model.predict(new_title())
    states = out["states"]
    assert [s["rank"] for s in states] == list(range(1, len(PILOT_STATES) + 1))
    assert sum(s["expected_share"] for s in states) == pytest.approx(1.0)
    assert all(
        s["low"] <= s["lift"] <= s["high"] for s in states
    )  # lift is log-scale: no floor at zero
    assert [s["lift"] for s in states] == sorted((s["lift"] for s in states), reverse=True)
    assert all(s["name"] == STATES[s["state"]] and len(s["drivers"]) == 3 for s in states)
    assert 0 <= out["confidence"] <= 100
    assert {"no_pre_release_demand", "small_training_set"} <= set(out["warnings"])


def test_comparables_are_older_and_from_other_franchises(model):
    out = model.predict(new_title(release=date(2016, 6, 1)))
    ids = {c["title_id"] for c in out["comparables"]}
    released = model.pool.set_index("title_id")["release_date"]
    assert all(released[i] < pd.Timestamp(2016, 6, 1) for i in ids)


def test_save_load_roundtrip_gives_same_prediction(model, tmp_path):
    folder = model.save(tmp_path)
    loaded = StateModel.load(tmp_path)
    assert loaded.version == model.version and (folder / "report.json").exists()
    a, b = model.predict(new_title()), loaded.predict(new_title())
    assert [s["lift"] for s in a["states"]] == pytest.approx([s["lift"] for s in b["states"]])


def test_load_without_model_is_a_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="no trained state model"):
        StateModel.load(tmp_path)


def test_predict_requires_a_release_date(model):
    with pytest.raises(ValueError):
        model.predict(new_title().assign(release_date=pd.NaT))


def test_one_off_title_frame_has_no_outcome_columns():
    frame = make_frame(
        "predict:x",
        "predict:x",
        "Demo",
        None,
        ["Action"],
        [],
        "anime_series",
        date(2030, 1, 1),
        "sword battle war hero " * 5,
    )
    assert not ({"popularity", "average_score", "share"} & set(frame.columns))
    assert frame["release_date"].iloc[0] == pd.Timestamp(2030, 1, 1)


# --- csv tables, label and leakage rules --------------------------------------
def test_csv_tables_are_consistent_and_leaky_outcomes_are_not_loaded():
    from app.ml import csv_data

    data = csv_data.load()
    assert data.check["max_abs_lift_diff"] < 1e-6 and data.check["demand_columns_all_pre"]
    assert data.check["labelled_titles_missing_features"] == []
    assert not (
        {"popularity", "favourites", "average_score", "log_popularity"} & set(data.titles.columns)
    )
    assert (data.labels.groupby("title_id")["share"].sum().round(6) == 1).all()


def test_state_effect_uses_only_the_given_titles():
    from app.ml.state_features import add_lift, state_effect, with_dlog

    labels = with_dlog(
        pd.DataFrame(
            {
                "title_id": ["a", "a", "b", "b"],
                "state": ["S1", "S2"] * 2,
                "share": [0.8, 0.2, 0.3, 0.7],
            }
        )
    )
    only_a, both = state_effect(labels[labels.title_id == "a"]), state_effect(labels)
    assert only_a["S1"] > 0 > only_a["S2"] and both["S1"] == pytest.approx(both["S2"] * -1)
    lifted = add_lift(labels, only_a)  # a state unseen in training gets effect 0, never an error
    assert lifted["y"].notna().all()


def test_history_only_counts_titles_whose_label_window_has_ended():
    from app.ml.state_features import history_features

    base = dict(
        franchise_id="f",
        genres=["X"],
        themes=[],
        format="TV",
        studio="Studio A",
        synopsis="s",
        episodes=12,
        has_streaming=False,
    )
    pool = pd.DataFrame([{**base, "title_id": "old", "release_date": pd.Timestamp("2020-01-01")}])
    labels = with_dlog_labels("old")
    emb = np.ones((1, 1))
    for days, expected in ((100, 0), (400, 1)):
        target = pd.DataFrame(
            [
                {
                    **base,
                    "title_id": "new",
                    "release_date": pd.Timestamp("2020-01-01") + pd.Timedelta(days=days),
                }
            ]
        )
        hist, _ = history_features(target, emb, pool, emb, labels, ["S1", "S2"])
        assert hist["parent_n"].max() == expected and hist["studio_n"].max() == expected
        assert (hist["parent_dlog"] != 0).any() == bool(expected)


def with_dlog_labels(title_id):
    from app.ml.state_features import with_dlog

    return with_dlog(
        pd.DataFrame({"title_id": [title_id] * 2, "state": ["S1", "S2"], "share": [0.9, 0.1]})
    )


def test_no_outcome_or_label_columns_are_features(model):
    banned = {"share", "log_share", "dlog", "lift", "y", "popularity", "average_score"}
    assert banned.isdisjoint(model.cols)
