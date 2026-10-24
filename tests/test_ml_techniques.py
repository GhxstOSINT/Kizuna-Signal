"""Tests for comparables, intervals, confidence, explanations and the franchise-grouped split.
Pipeline-level checks use SYNTHETIC labels, so they prove plumbing and invariants, not model quality."""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from app.ml.comparables import ComparableIndex, comparable_features
from app.ml.embeddings import TfidfSvdEmbedder, get_embedder
from app.ml.explain import contributions, global_by_group
from app.ml.features import titles_frame
from app.ml.intervals import ConformalInterval
from app.ml.split import franchise_time_split
from app.ml.states import PILOT_STATES
from app.ml.train import run as train_run
from app.ml.train import save
from tests.test_ml_pipeline import synthetic


def frame(rows):
    return pd.DataFrame(rows).assign(release_date=lambda d: pd.to_datetime(d["release_date"]))


def test_franchise_stays_on_one_side_of_the_split():
    titles = frame([{"title_id": f"t{i}", "franchise_id": f"f{i // 3}",
                     "release_date": date(2016 + i // 6, 1 + i % 6, 1)} for i in range(30)])
    train, test = franchise_time_split(titles, 0.2)
    train_f = set(titles[titles.title_id.isin(train)].franchise_id)
    test_f = set(titles[titles.title_id.isin(test)].franchise_id)
    assert train_f.isdisjoint(test_f) and train | test == set(titles.title_id)
    first = titles.groupby("franchise_id").release_date.min()
    assert first[list(train_f)].max() <= first[list(test_f)].min()


def test_comparables_are_older_and_from_other_franchises():
    titles = frame([
        {"title_id": "old", "franchise_id": "a", "release_date": date(2016, 1, 1), "genres": ["Action"], "format": "TV"},
        {"title_id": "sib", "franchise_id": "b", "release_date": date(2017, 1, 1), "genres": ["Action"], "format": "TV"},
        {"title_id": "new", "franchise_id": "b", "release_date": date(2018, 1, 1), "genres": ["Action"], "format": "TV"},
        {"title_id": "future", "franchise_id": "c", "release_date": date(2020, 1, 1), "genres": ["Action"], "format": "TV"},
    ])
    emb = np.tile(np.array([1.0, 0.0]), (4, 1))  # identical embeddings: only the rules can exclude
    index = ComparableIndex(titles, emb)
    found = [titles.title_id[i] for i, _, _ in index.find(titles.iloc[2], emb[2])]
    assert found == ["old"]  # 'sib' shares the franchise, 'future' is newer


def test_comparable_feature_uses_neighbour_labels():
    titles = frame([
        {"title_id": "a", "franchise_id": "a", "release_date": date(2016, 1, 1), "genres": ["X"], "format": "TV"},
        {"title_id": "b", "franchise_id": "b", "release_date": date(2018, 1, 1), "genres": ["X"], "format": "TV"},
    ])
    emb = np.ones((2, 1))
    labels = pd.DataFrame([{"title_id": "a", "state": "S1", "share": 0.7}, {"title_id": "a", "state": "S2", "share": 0.3},
                           {"title_id": "b", "state": "S1", "share": 0.1}, {"title_id": "b", "state": "S2", "share": 0.9}])
    rows, stats = comparable_features(ComparableIndex(titles, emb), titles, emb, labels, ["S1", "S2"])
    b = rows[rows.title_id == "b"].set_index("state")["cmp_share"]
    assert b["S1"] == pytest.approx(0.7) and b["S2"] == pytest.approx(0.3)  # b borrows from a, not itself
    assert np.isnan(rows[rows.title_id == "a"]["cmp_share"]).all()  # nothing older than a
    assert stats.set_index("title_id").loc["a", "cmp_count"] == 0


def test_conformal_interval_reaches_nominal_coverage():
    rng = np.random.default_rng(0)
    y = rng.uniform(0.2, 0.8, size=2000)  # shares are non-negative; the lower bound is clipped at 0
    pred = np.full(2000, 0.5)
    c = ConformalInterval(0.2).fit(y[:1000], pred[:1000])
    assert 0.76 - 0.02 <= c.coverage(y[1000:], pred[1000:]) <= 0.84 + 0.02  # nominal 0.8, ~3 sd of sampling noise
    lo, hi = c.predict(np.array([0.0]))
    assert lo[0] == 0 and hi[0] == pytest.approx(c.q_)


def test_embedder_fallback_and_unit_norm():
    emb = get_embedder("tfidf")
    assert isinstance(emb, TfidfSvdEmbedder)
    texts = ["sword battle war hero", "love school heart", "robot pilot giant", "funny gag friends"] * 3
    vecs = emb.fit(texts).embed(texts)
    assert np.allclose(np.linalg.norm(vecs, axis=1), 1.0)


def test_full_report_contents_and_artifacts(tmp_path):
    recs, lab = synthetic(80)
    report, objects, _ = train_run(titles_frame(recs), lab, PILOT_STATES)
    assert report["n_fit_titles"] + report["n_calibration_titles"] == report["n_train_titles"]
    assert set(report["metrics"]) == {"state_mean", "ridge_genre_state", "xgboost", "ensemble"}
    assert 0 <= report["intervals"]["observed"] <= 1 and report["intervals"]["nominal"] == 0.8
    assert set(report["component_importance"]) == {"content", "demand", "regional", "comparable"}
    assert sum(report["component_importance"].values()) == pytest.approx(1.0)
    assert report["example_explanation"]["top_features"]
    assert "engagement_quality" in report and report["scoring_config"]["content_fit"] == 0.25
    folder = save(report, tmp_path, objects)
    assert (folder / "model.joblib").exists() and (folder / "report.json").exists()
    assert (tmp_path / "initial_report.json").exists()


def test_shap_contributions_add_up_to_the_prediction():
    recs, lab = synthetic(60)
    report, objects, _ = train_run(titles_frame(recs), lab, PILOT_STATES)
    xgb, cols = objects["models"]["xgboost"], objects["cols"]
    rows = pd.DataFrame(np.random.default_rng(0).random((5, len(cols))), columns=cols)
    contrib = contributions(xgb, rows, cols)
    bias = xgb.model_.get_booster().predict(__import__("xgboost").DMatrix(rows, feature_names=cols),
                                            pred_contribs=True)[:, -1]
    assert np.allclose(contrib.sum(axis=1) + bias, xgb.predict(rows, cols), atol=1e-4)
    assert sum(global_by_group(contrib).values()) == pytest.approx(1.0)


def test_comparable_share_feature_never_uses_the_titles_own_label():
    recs, lab = synthetic(60)
    # If a title's own label leaked into cmp_share, corrupting only that title's labels would change it.
    base_rep, base_obj, _ = train_run(titles_frame(recs), lab, PILOT_STATES)
    tid = "t59"
    corrupted = lab.copy()
    corrupted.loc[corrupted.title_id == tid, "share"] = corrupted.loc[corrupted.title_id == tid, "share"].values[::-1]
    from app.ml.features import ContentEncoder
    titles = titles_frame(recs)
    enc = ContentEncoder().fit(titles)
    emb = enc.embed(titles)
    idx = ComparableIndex(titles, emb)
    a, _ = comparable_features(idx, titles, emb, lab, PILOT_STATES)
    b, _ = comparable_features(idx, titles, emb, corrupted, PILOT_STATES)
    pd.testing.assert_frame_equal(a[a.title_id == tid].reset_index(drop=True),
                                  b[b.title_id == tid].reset_index(drop=True))
