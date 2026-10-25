from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def _analysis(client, title_id):
    started = client.post(f"/api/v1/titles/{title_id}/analyses").json()
    return started["analysis_id"]


def _scenario(client, analysis_id, **overrides):
    response = client.post(
        f"/api/v1/analyses/{analysis_id}/scenarios", json={"name": "Test scenario", **overrides}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_scenario_without_changes_reproduces_the_base(client, created_title):
    analysis_id = _analysis(client, created_title["id"])
    result = _scenario(client, analysis_id)["result"]
    assert result["score_delta"] == pytest.approx(0, abs=0.01)
    assert result["confidence_delta"] == pytest.approx(0, abs=0.01)


def test_more_languages_raise_the_score_through_census_coverage(client, created_title):
    analysis_id = _analysis(client, created_title["id"])
    narrow = _scenario(client, analysis_id, target_languages=["Hindi"])["result"]
    broad = _scenario(
        client, analysis_id, target_languages=["Hindi", "Tamil", "Telugu", "Bengali", "Marathi"]
    )["result"]
    assert broad["score_delta"] > narrow["score_delta"]


def test_platform_budget_and_localization_mode_do_not_move_the_score(client, created_title):
    analysis_id = _analysis(client, created_title["id"])
    changed = _scenario(
        client,
        analysis_id,
        target_platform="Theatrical",
        marketing_budget="high",
        localization_mode="multilingual_dub",
    )["result"]
    assert changed["score_delta"] == pytest.approx(0, abs=0.01)
    assert changed["cost_level"] == "high"  # they still change the cost label and the plan


def test_disabling_a_source_lowers_confidence(client, created_title):
    analysis_id = _analysis(client, created_title["id"])
    result = _scenario(client, analysis_id, disabled_sources=["wikimedia", "youtube"])["result"]
    assert result["confidence_delta"] < 0


def test_scenario_response_includes_a_creation_timestamp(client, created_title):
    analysis_id = _analysis(client, created_title["id"])
    scenario = _scenario(client, analysis_id)
    assert scenario["created_at"].endswith("Z")
    listed = client.get(f"/api/v1/analyses/{analysis_id}/scenarios").json()
    assert listed[0]["created_at"] == scenario["created_at"]
