"""State model + scoring wiring. Training data is SYNTHETIC, so these prove plumbing and invariants
(no leakage, stable output shape, idempotent storage, failure handling), not predictive quality."""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from app.db.models import Analysis, Job, RegionalScore, Title, TitleAssumption
from app.ml.features import titles_frame
from app.ml.schema import TitleRecord
from app.ml.state_model import StateModel
from app.ml.states import PILOT_STATES, STATES
from app.services import state_scoring
from tests.test_ml_pipeline import synthetic


@pytest.fixture(scope="module")
def model():
    records, labels = synthetic(60)
    return StateModel.train(titles_frame(records), labels, PILOT_STATES)


def new_title(release=date(2030, 1, 1), genre="Action"):
    return titles_frame([TitleRecord(
        title_id="new", franchise_id="new", genres=[genre], themes=[genre.lower()], format="TV",
        original_release_date=release, synopsis="sword battle war hero story adventure")])


def test_report_describes_out_of_fold_evaluation_and_small_data(model):
    r = model.report
    assert r["task"] == "state" and r["n_labelled_titles"] == 60 and r["oof_titles"] < 60
    assert set(r["metrics_oof"]) == {"state_mean", "ridge_genre_state", "xgboost", "ensemble"}
    assert r["exploratory"] is True and r["ensemble_weights"]["ridge"] + r["ensemble_weights"]["xgboost"] == pytest.approx(1)
    assert sum(r["titles_per_state"].values()) == 60 * len(PILOT_STATES)


def test_prediction_shape_and_invariants(model):
    out = model.predict(new_title())
    states = out["states"]
    assert [s["rank"] for s in states] == list(range(1, len(PILOT_STATES) + 1))
    assert sum(s["share"] for s in states) == pytest.approx(1.0)
    assert all(s["low"] <= s["share"] <= s["high"] and s["low"] >= 0 for s in states)
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
    assert [s["share"] for s in a["states"]] == pytest.approx([s["share"] for s in b["states"]])


def test_load_without_model_is_a_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="no trained state model"):
        StateModel.load(tmp_path)


def test_predict_requires_a_release_date(model):
    with pytest.raises(ValueError):
        model.predict(new_title().assign(release_date=pd.NaT))


# --- scoring service, without a database -------------------------------------
class FakeDB:
    def __init__(self, title, assumption, job):
        self.rows, self.deleted, self.title, self.assumption, self.job = [], [], title, assumption, job

    def get(self, cls, _id):
        return {Title: self.title, Job: self.job}[cls]

    def scalar(self, _stmt):
        return self.assumption

    def scalars(self, _stmt):
        return iter([])

    def add(self, row):
        self.rows.append(row)

    def delete(self, row):
        self.deleted.append(row)

    def commit(self):
        pass

    def rollback(self):
        pass


def fixtures():
    title = Title(id=5, name_en="Demo", synopsis="sword battle war hero " * 5, genres=["Action"],
                  format="anime_series", franchise=None, release_date=None)
    assumption = TitleAssumption(title_id=5, target_states=["IN-MH"], planned_launch_date=date(2030, 1, 1))
    return title, assumption, Job(id=1, job_type="analysis", status="queued", payload={})


def test_run_analysis_fills_results_and_regional_rows(model):
    title, assumption, job = fixtures()
    analysis = Analysis(id=9, title_id=5, job_id=1, status="queued")
    db = FakeDB(title, assumption, job)
    state_scoring.run_analysis(db, analysis, model)
    assert analysis.status == "succeeded" and analysis.result_version == model.version
    assert analysis.market_potential is None  # not this model's job
    assert job.status == "succeeded" and job.result["analysis_id"] == 9
    regions = [r for r in db.rows if isinstance(r, RegionalScore)]
    assert len(regions) == len(PILOT_STATES) and {r.region_type for r in regions} == {"state"}
    assert [r.evidence[0]["in_target"] for r in regions if r.region_code == "IN-MH"] == [True]
    assert analysis.provenance_summary["task"] == "state"


def test_failure_marks_job_and_analysis_failed(model, monkeypatch):
    title, assumption, job = fixtures()
    analysis = Analysis(id=9, title_id=5, job_id=1, status="queued")
    monkeypatch.setattr(state_scoring, "score", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    state_scoring.run_analysis(FakeDB(title, assumption, job), analysis, model)
    assert analysis.status == "failed" and job.status == "failed"
    assert job.error_code == "RuntimeError" and "boom" in job.error_message


def test_dummy_title_frame_has_no_outcome_columns():
    title, assumption, _ = fixtures()
    frame = state_scoring.to_frame(title, assumption)
    assert not ({"popularity", "average_score", "share"} & set(frame.columns))
    assert frame["release_date"].iloc[0] == pd.Timestamp(2030, 1, 1)
