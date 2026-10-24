from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.schemas.asset import AssetCreate
from app.schemas.assumption import AssumptionIn
from app.schemas.title import TitleCreate
from app.services.completeness import evaluate

client = TestClient(app)

VALID_ASSUMPTION = {
    "distribution_model": "ott",
    "localization_mode": "subtitled_and_dubbed",
    "languages": ["HI", "ta", "hi"],
    "launch_geography": "national",
}
VALID_ASSET = {
    "asset_type": "poster",
    "filename": "poster.png",
    "storage_uri": "s3://kizuna/posters/poster.png",
    "mime_type": "image/png",
    "size_bytes": 1024,
}


# --- titles ------------------------------------------------------------------
def test_title_requires_project_and_name():
    assert client.post("/api/v1/titles", json={"name_en": "X"}).status_code == 422
    assert client.post("/api/v1/titles", json={"project_id": 1}).status_code == 422


def test_title_rejects_unknown_format():
    with pytest.raises(ValidationError):
        TitleCreate(project_id=1, name_en="X", format="podcast")


def test_title_lists_are_cleaned():
    t = TitleCreate(project_id=1, name_en="X", genres=[" Action", "action", " "])
    assert t.genres == ["Action"]


# --- projects ----------------------------------------------------------------
def test_project_rejects_blank_name():
    assert client.post("/api/v1/projects", json={"name": ""}).status_code == 422


# --- assets ------------------------------------------------------------------
def test_asset_valid():
    assert AssetCreate(**VALID_ASSET).asset_type == "poster"


@pytest.mark.parametrize(
    "patch",
    [
        {"mime_type": "video/mp4"},  # wrong type for poster
        {"size_bytes": 21 * 1024 * 1024},  # over poster limit
        {"size_bytes": 0},
        {"filename": "../etc/passwd"},
        {"storage_uri": "file:///tmp/x.png"},
        {"checksum_sha256": "abc"},
        {"asset_type": "banner"},
    ],
)
def test_asset_rejected(patch):
    with pytest.raises(ValidationError):
        AssetCreate(**{**VALID_ASSET, **patch})


# --- assumptions -------------------------------------------------------------
def test_assumption_normalises_languages():
    assert AssumptionIn(**VALID_ASSUMPTION).languages == ["hi", "ta"]


@pytest.mark.parametrize(
    "patch",
    [
        {"languages": []},
        {"languages": [" "]},
        {"languages": ["hindi"]},
        {"launch_geography": "selected_states"},  # states required
        {"launch_geography": "regional_first", "target_states": []},
        {"target_states": ["Kerala"]},  # states forbidden for national
        {"distribution_model": "cable"},
    ],
)
def test_assumption_rejected(patch):
    with pytest.raises(ValidationError):
        AssumptionIn(**{**VALID_ASSUMPTION, **patch})


def test_assumption_requires_core_fields():
    for field in ("distribution_model", "localization_mode", "languages", "launch_geography"):
        body = {k: v for k, v in VALID_ASSUMPTION.items() if k != field}
        assert client.put("/api/v1/titles/1/assumptions", json=body).status_code == 422


# --- completeness ------------------------------------------------------------
def _title(**kw):
    base = dict(
        synopsis="A" * 60, genres=["Action"], format="anime_series", studio="Madhouse",
        name_jp="x", franchise="f", cast_members=["a"], release_date="2027-01-01",
    )
    return SimpleNamespace(**{**base, **kw})


def test_empty_title_is_not_ready():
    r = evaluate(_title(synopsis=None, genres=[], format=None, studio=None), [], None)
    assert not r.ready_for_analysis
    assert {m.field for m in r.missing_required} == {
        "synopsis", "genres", "format", "studio", "assumptions",
    }


def test_short_synopsis_counts_as_missing():
    r = evaluate(_title(synopsis="too short"), [], SimpleNamespace(marketing_budget_band=None, planned_launch_date=None))
    assert [m.field for m in r.missing_required] == ["synopsis"]


def test_complete_title_scores_one():
    assets = [SimpleNamespace(asset_type="poster"), SimpleNamespace(asset_type="trailer")]
    assumption = SimpleNamespace(marketing_budget_band="low", planned_launch_date="2027-01-01")
    r = evaluate(_title(), assets, assumption)
    assert r.ready_for_analysis and r.score == 1.0
    assert not r.missing_required and not r.missing_recommended


def test_recommended_gaps_do_not_block_analysis():
    assumption = SimpleNamespace(marketing_budget_band=None, planned_launch_date=None)
    r = evaluate(_title(), [], assumption)
    assert r.ready_for_analysis
    assert {m.field for m in r.missing_recommended} >= {"assets.poster", "assets.trailer"}
    assert r.score < 1.0
