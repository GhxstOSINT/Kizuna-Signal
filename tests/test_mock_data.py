import json

import pytest

from kizuna import intake
from kizuna.api import MockApi
from kizuna.config import GEO_PATH, MOCK_DIR

TITLES = ["shadow_bloom", "hollow_tide", "kitsune_circuit"]


@pytest.fixture(scope="module")
def api():
    return MockApi(stage_seconds=0)


def geo_names():
    return {f["properties"]["ST_NM"] for f in json.loads(GEO_PATH.read_text())["features"]}


def test_files_exist_for_every_title():
    for tid in TITLES:
        for name in ["title", "analysis", "regions", "comparables", "sources", "scenarios", "recommendation"]:
            assert (MOCK_DIR / tid / f"{name}.json").exists()


def test_region_names_match_geojson_exactly(api):
    names = geo_names()
    for tid in TITLES:
        regions = api.get_regions(tid)["regions"]
        assert {r["state"] for r in regions} == names
    cfg = api.get_config()
    assert set(cfg["states"]) == names


def test_no_delhi_ncr_anywhere():
    for path in MOCK_DIR.rglob("*.json"):
        assert "delhi ncr" not in path.read_text(encoding="utf-8").lower(), path


def test_comparable_sets_reference_existing_comparables_and_have_five(api):
    for tid in TITLES:
        c = api.get_comparables(tid)
        ids = {x["id"] for x in c["comparables"]}
        for name, members in c["sets"].items():
            assert len(members) == 5, (tid, name)
            assert set(members) <= ids


def test_sources_cover_the_five_public_sources(api):
    for tid in TITLES:
        ids = {s["id"] for s in api.get_sources(tid)}
        assert {"anilist", "google_trends", "youtube", "wikimedia", "census"} <= ids


def test_partial_title_has_unavailable_toggle_locked(api):
    yt = next(s for s in api.get_sources("kitsune_circuit") if s["id"] == "youtube")
    assert yt["status"] == "unavailable" and yt["toggleable"] is False


def test_scenario_levers_exist_in_config(api):
    cfg = api.get_config()
    for tid in TITLES:
        sc = api.get_scenarios(tid)
        for levers in [sc["base"]["levers"]] + [p["levers"] for p in sc["presets"]]:
            for lever, option in levers.items():
                assert option in cfg["levers"][lever]["options"]


def test_driver_sources_exist(api):
    for tid in TITLES:
        src_ids = {s["id"] for s in api.get_sources(tid)}
        for d in api.get_analysis(tid)["drivers"]:
            assert set(d["source_ids"]) <= src_ids


def test_project_list_has_three_seed_titles(api):
    assert [p["title_id"] for p in api.list_projects()] == TITLES


VALID = {"title": "Test", "synopsis": "Something", "format": "Anime series", "primary_genre": "Fantasy",
         "source_material": "Original", "release_period": "March 2027", "target_platform": "OTT"}


def test_intake_validation_and_completeness():
    assert intake.validate(VALID) == []
    assert len(intake.validate({})) == 7
    assert intake.validate(dict(VALID, trailer_url="javascript:alert(1)"))
    pct, missing = intake.completeness(VALID)
    assert 0 < pct < 100 and "Studio" in missing
    assert intake.completeness({})[0] == 0


def test_start_analysis_normal_partial_failure_flows():
    api = MockApi(stage_seconds=0)
    job = api.start_analysis(dict(VALID, primary_genre="Fantasy"), outcome="normal")
    j = api.get_job(job)
    assert j["status"] == "complete" and j["progress"] == 100
    pid = j["title_id"]
    assert pid in [p["title_id"] for p in api.list_projects()]
    assert api.get_analysis(pid)["mock_notice"]

    pj = api.get_job(api.start_analysis(VALID, outcome="partial"))
    assert pj["status"] == "partial"
    assert any(s["status"] == "unavailable" for s in api.get_sources(pj["title_id"]))

    fj = api.start_analysis(VALID, outcome="failure")
    failed = api.get_job(fj)
    assert failed["status"] == "failed" and failed["error"]
    assert failed["title_id"] not in [p["title_id"] for p in api.list_projects()]
    api.retry_job(fj)
    assert api.get_job(fj)["status"] == "complete"

    fj2 = api.start_analysis(VALID, outcome="failure")
    api.get_job(fj2)
    api.use_cached_data(fj2)
    assert api.get_job(fj2)["status"] == "partial"


def test_start_analysis_rejects_invalid_payload():
    with pytest.raises(ValueError):
        MockApi(stage_seconds=0).start_analysis({"title": "x"})


def test_api_returns_private_copies(api):
    a = api.get_analysis("shadow_bloom")
    a["components"]["content_fit"] = 0
    assert api.get_analysis("shadow_bloom")["components"]["content_fit"] == 83
