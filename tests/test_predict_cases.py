import csv
import io
import warnings
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.skipif(
    not Path("models/state/LATEST.json").exists(), reason="no trained state model"
)
warnings.filterwarnings("ignore")

SYNOPSIS = (
    "A young swordsman loses his village to a demon army and sets out across a ruined kingdom "
    "to avenge his family and find the dawn blade."
)
BASE = {
    "name_en": "Blade of Dawn",
    "genres": ["Action", "Fantasy"],
    "tags": ["Swordplay"],
    "synopsis": SYNOPSIS,
    "release_date": "2026-10-24",
    "episodes": 24,
}


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def predict(client, **override):
    return client.post("/api/v1/predict", json={**BASE, **override})


def test_response_invariants(client):
    out = predict(client).json()
    states = out["states"]
    assert len(states) == 35  # every scored state and UT
    assert sum(s["expected_share"] for s in states) == pytest.approx(1.0, abs=1e-6)
    assert [s["rank"] for s in states] == list(range(1, len(states) + 1))
    assert all(s["low"] <= s["lift"] <= s["high"] for s in states)
    assert 0 <= out["india"]["confidence"] <= 100 and 0 <= out["success"]["score"] <= 100
    assert out["india"]["top_states"] == [s["state"] for s in states[:5]]


def test_prediction_is_deterministic(client):
    assert predict(client).json()["states"] == predict(client).json()["states"]


@pytest.mark.parametrize(
    "override",
    [
        {"synopsis": "too short"},
        {"genres": []},
        {"episodes": 0},
        {"minutes_per_episode": -5},
        {"release_date": "not-a-date"},
        {"languages": ["zz-nonsense"]},
        {"name_en": ""},
        {"name_en": "x" * 300},
        {"format": "anime_movie"},
        {"localization_mode": "voiceover"},
    ],
)
def test_invalid_input_is_rejected_with_422(client, override):
    assert predict(client, **override).status_code == 422


@pytest.mark.parametrize(
    "override",
    [
        {"synopsis": SYNOPSIS * 60},
        {"name_en": "ブレード・オブ・ドーン 夜明け"},
        {"episodes": None, "tags": []},
        {"studio": None, "release_date": None},
        {"format": "anime_film", "episodes": 1, "minutes_per_episode": 110},
        {"languages": ["hi", "ta"], "localization_mode": "dubbed"},
        {"foo": 1},
    ],
)
def test_unusual_but_valid_input_succeeds(client, override):
    r = predict(client, **override)
    assert r.status_code == 200, r.text


def test_placeholder_synopsis_lowers_confidence(client):
    junk = predict(client, synopsis="string" * 9).json()["india"]
    real = predict(client).json()["india"]
    assert junk["confidence"] < real["confidence"]
    assert "unlike_training_titles" in junk["warnings"]


def test_unknown_genre_is_flagged_not_silent(client):
    warnings_ = predict(client, genres=["Action", "Western"]).json()["india"]["warnings"]
    assert any(w.startswith("unknown_genres") and "Western" in w for w in warnings_)
    assert not any(
        w.startswith("unknown_genres") for w in predict(client).json()["india"]["warnings"]
    )


def test_release_date_changes_the_prediction(client):
    old = predict(client, release_date="2019-04-01").json()
    new = predict(client).json()
    assert old["states"] != new["states"]


def test_genre_changes_the_score_and_ranking(client):
    action = predict(client).json()
    comedy = predict(client, genres=["Comedy"], tags=[]).json()
    assert action["success"]["score"] != comedy["success"]["score"]
    assert action["india"]["top_states"] != comedy["india"]["top_states"]


def test_duplicate_and_mixed_case_genres_are_collapsed(client):
    a = predict(client, genres=["Action", "action", " Action "]).json()
    b = predict(client, genres=["Action"]).json()
    assert a["states"] == b["states"]


def test_synthetic_rows_are_reported_per_state(client):
    out = predict(client).json()
    card = client.get("/api/v1/model").json()
    assert (
        sum(s["synthetic_rows"] for s in out["states"]) == card["training_data"]["synthetic_rows"]
    )


@pytest.mark.parametrize(
    "fmt,start", [("json", b"{"), ("pdf", b"%PDF-"), ("xml", b"<?xml"), ("csv", b"")]
)
def test_report_formats(client, fmt, start):
    r = client.post(f"/api/v1/predict/report?format={fmt}", json=BASE)
    assert r.status_code == 200 and r.content.lstrip(b"\xef\xbb\xbf").startswith(start)
    if fmt == "csv":
        assert len(list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))) == 35


def test_unknown_report_format_is_rejected(client):
    assert client.post("/api/v1/predict/report?format=docx", json=BASE).status_code == 422


def _conf(client, **override):
    return predict(client, **override).json()["india"]


def test_confidence_responds_to_how_much_was_supplied(client):
    rich = _conf(
        client,
        tags=["Swordplay", "Demons", "Male Protagonist"],
        studio="ufotable",
        episodes=24,
        minutes_per_episode=24,
    )
    bare = _conf(client, tags=[], studio=None, episodes=None)
    assert (
        rich["confidence_factors"]["completeness"]
        > bare["confidence_factors"]["completeness"] + 0.2
    )
    assert rich["confidence"] > bare["confidence"]


def test_no_confidence_factor_is_constant_across_inputs(client):
    runs = [
        _conf(client, **o)
        for o in (
            {},
            {"genres": ["Comedy"], "tags": []},
            {"tags": [], "studio": None, "episodes": None},
            {"synopsis": "string" * 9},
        )
    ]
    for factor in ("completeness", "comparables", "agreement", "ood"):
        assert len({r["confidence_factors"][factor] for r in runs}) > 1, factor
    assert len({r["confidence"] for r in runs}) == len(runs)


def test_confidence_weights_sum_to_one():
    from dataclasses import asdict

    from app.ml.scoring_config import ConfidenceConfig

    weights = {k: v for k, v in asdict(ConfidenceConfig()).items() if k != "version"}
    assert sum(weights.values()) == pytest.approx(1.0)


def test_rating_is_a_0_to_100_percentile_that_spreads_wider_than_the_raw_score(client):
    ratings, raws = [], []
    for o in (
        {},
        {"genres": ["Comedy"], "tags": []},
        {"genres": ["Romance", "Drama"], "tags": []},
        {"genres": ["Mecha", "Sci-Fi"], "tags": []},
        {"genres": ["Horror", "Psychological"], "tags": []},
    ):
        s = predict(client, **o).json()["success"]
        assert 0 <= s["rating_low"] <= s["rating"] <= s["rating_high"] <= 100
        assert s["rating_band"] in ("top quarter", "middle half", "bottom quarter")
        ratings.append(s["rating"]), raws.append(s["score"])
    assert max(ratings) - min(ratings) > max(raws) - min(raws)


def test_rating_is_monotonic_in_the_raw_score(client):
    pts = sorted(
        (s["score"], s["rating"])
        for s in (
            predict(client, genres=g, tags=[]).json()["success"]
            for g in (["Action"], ["Comedy"], ["Horror"], ["Sports"])
        )
    )
    assert [r for _, r in pts] == sorted(r for _, r in pts)
