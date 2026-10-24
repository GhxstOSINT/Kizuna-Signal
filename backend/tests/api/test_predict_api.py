"""POST /api/v1/predict. Uses a SYNTHETIC state model and a fake Trends fetcher: proves the contract."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.adapters.google_trends import TrendsClient
from app.api.routes import predict as predict_routes
from app.api.routes.predict import get_state_model, get_trends_client
from app.main import app
from app.ml.features import titles_frame
from app.ml.state_model import StateModel
from app.ml.states import PILOT_STATES
from tests.support.ml_data import synthetic

BODY = {
    "name_en": "Blade of Dawn",
    "genres": ["Action", "Fantasy"],
    "tags": ["Male Protagonist"],
    "synopsis": "A young swordsman fights demons across a ruined kingdom to save his sister " * 2,
    "studio": "Studio A",
    "release_date": "2030-04-01",
    "episodes": 12,
}


@pytest.fixture(scope="module")
def model():
    records, labels = synthetic(60)
    return StateModel.train(titles_frame(records), labels, PILOT_STATES, min_theme_titles=1)


def fetcher(terms, geo, start, end):
    level = 30 if "dubbed" in terms[0] else 12
    rows, day = [], start
    while day <= end:
        rows.append(
            {"date": day.isoformat(), "values": {terms[0]: level, terms[1]: 50}, "partial": False}
        )
        day += timedelta(weeks=1)
    return rows


@pytest.fixture()
def client(model, tmp_path, monkeypatch):
    monkeypatch.setattr(
        predict_routes.settings, "models_dir", str(tmp_path / "models")
    )  # keep caches out of the repo
    app.dependency_overrides[get_state_model] = lambda: model
    app.dependency_overrides[get_trends_client] = lambda: TrendsClient(
        fetcher=fetcher, raw_dir=tmp_path, sleep=lambda s: None
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_one_request_returns_ranked_states_and_summary(client, model):
    r = client.post("/api/v1/predict", json=BODY)
    assert r.status_code == 200
    out = r.json()
    states = out["states"]
    assert out["model_version"] == model.version and out["title"] == "Blade of Dawn"
    assert [s["rank"] for s in states] == list(range(1, len(PILOT_STATES) + 1))
    assert sum(s["expected_share"] for s in states) == pytest.approx(1.0)
    assert out["india"]["top_states"] == [s["state"] for s in states[:5]]
    assert out["india"]["bottom_states"] == [s["state"] for s in states[-5:]]
    assert (
        0 <= out["india"]["confidence"] <= 100
        and "no single national score" in out["india"]["note"]
    )
    assert {"small_training_set", "no_pre_release_demand"} <= set(out["india"]["warnings"])
    assert out["seo"] is None and "market_potential" not in out


def test_tags_and_genres_reach_the_model_features(model):
    from datetime import date

    from app.services.state_frame import make_frame

    frame = make_frame(
        "p", "p", "X", None, ["Action"], ["action"], "anime_series", date(2030, 1, 1), "s " * 30
    )
    encoded = model.encoder.transform(frame).iloc[0]
    assert (
        encoded["theme_action"] == 1 and encoded["genre_Action"] == 1 and encoded["format_TV"] == 1
    )


def test_include_seo_ranks_terms_and_measures_top_states(client):
    r = client.post(
        "/api/v1/predict",
        json={**BODY, "include_seo": True, "languages": ["hi"], "localization_mode": "dubbed"},
    )
    seo = r.json()["seo"]
    assert seo["best_term"] == "Blade of Dawn Hindi dubbed"
    assert [f["state"] for f in seo["state_focus"]] == [s["state"] for s in r.json()["states"][:3]]
    assert all(f["term_ratio"] is not None for f in seo["state_focus"])


@pytest.mark.parametrize(
    "change",
    [
        {"genres": []},
        {"synopsis": "too short"},
        {"name_en": ""},
        {"format": "podcast"},
        {"languages": ["hindi"]},
        {"episodes": 0},
        {"release_date": "soon"},
    ],
)
def test_bad_input_is_rejected_with_422(client, change):
    assert client.post("/api/v1/predict", json={**BODY, **change}).status_code == 422


def test_missing_model_gives_clear_503(tmp_path, monkeypatch):
    from app.api.routes import predict as predict_routes

    monkeypatch.setattr(predict_routes.settings, "models_dir", str(tmp_path))
    predict_routes._load_model.cache_clear()
    r = TestClient(app).post("/api/v1/predict", json=BODY)
    assert r.status_code == 503 and "train_state_model" in r.json()["error"]["message"]
