from fastapi.testclient import TestClient

from app.main import app
from app.ml import regional
from app.ml.census import STATES, top_states


def _predict(genre, fmt="series", platform="ott", budget="medium", languages=()):
    return regional.predict_states(
        [genre], fmt, platform, budget, list(languages),
        state_languages={"Tamil Nadu": "Tamil", "Uttar Pradesh": "Hindi"},
    )


def test_artifact_documents_a_million_plus_synthetic_rows():
    card = regional.load()
    assert card["dataset"]["rows"] >= 1_000_000 and card["dataset"]["synthetic"] is True
    assert card["metrics"]["holdout_r2"] <= card["metrics"]["r2_ceiling"] + 0.01


def test_top_states_are_census_ranked():
    assert top_states() == {"Uttar Pradesh", "Maharashtra", "West Bengal", "Tamil Nadu"}


def test_soap_style_genre_scores_higher_in_south_and_hindi_belt():
    soap = _predict("family_drama", "soap_opera", "broadcast_tv")
    scifi = _predict("scifi", "soap_opera", "broadcast_tv")
    assert soap["Tamil Nadu"]["demand"] > scifi["Tamil Nadu"]["demand"]
    assert soap["Uttar Pradesh"]["demand"] > scifi["Uttar Pradesh"]["demand"]


def test_predictions_are_bounded_and_complete():
    out = _predict("action", budget="high", languages=["Tamil"])
    assert set(out) == set(STATES)
    for row in out.values():
        low, high = row["interval_80"]
        assert 0 <= low <= row["demand"] <= high <= 100


def test_language_match_and_budget_raise_demand():
    base = _predict("action", budget="low")["Tamil Nadu"]["demand"]
    assert _predict("action", budget="high")["Tamil Nadu"]["demand"] > base
    assert _predict("action", budget="low", languages=["Tamil"])["Tamil Nadu"]["demand"] > base


def test_model_card_endpoint():
    body = TestClient(app).get("/api/v1/model/card").json()
    assert body["active"] is True and body["dataset"]["rows"] >= 1_000_000
