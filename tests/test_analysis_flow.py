def start_and_read_analysis(client, title_id, body=None):
    started = client.post(f"/api/v1/titles/{title_id}/analyses", json=body)
    assert started.status_code == 202, started.text
    identifiers = started.json()
    job = client.get(f"/api/v1/jobs/{identifiers['job_id']}")
    assert job.status_code == 200
    assert job.json()["progress"] == 100
    analysis = client.get(f"/api/v1/analyses/{identifiers['analysis_id']}")
    assert analysis.status_code == 200
    return analysis.json()


def test_complete_analysis_returns_frontend_contract(client, created_title):
    analysis = start_and_read_analysis(client, created_title["id"])
    assert analysis["status"] == "completed"
    result = analysis["result"]
    assert 0 <= result["market_potential_score"] <= 100
    assert result["confidence_level"] in {"low", "medium", "high"}
    assert len(result["regional_scores"]) >= 5
    assert len(result["comparable_titles"]) == 5
    assert result["positive_drivers"]
    assert result["recommendation"]["priority_markets"]
    assert result["model_version"]
    assert result["feature_version"]
    assert result["scoring_version"]


def test_missing_source_produces_partial_result_and_confidence_penalty(client, created_title):
    complete = start_and_read_analysis(client, created_title["id"])
    partial = start_and_read_analysis(
        client,
        created_title["id"],
        {"disabled_sources": ["youtube"]},
    )
    assert partial["status"] == "partially_completed"
    assert partial["result"]["confidence_score"] < complete["result"]["confidence_score"]
    youtube = next(
        item for item in partial["result"]["source_status"] if item["source"] == "youtube"
    )
    assert youtube["status"] == "unavailable"
    assert any("youtube" in warning.lower() for warning in partial["warnings"])


def test_scenario_reports_score_and_confidence_deltas(client, created_title):
    analysis = start_and_read_analysis(client, created_title["id"])
    analysis_id = analysis["id"]
    response = client.post(
        f"/api/v1/analyses/{analysis_id}/scenarios",
        json={
            "name": "Multilingual OTT rollout",
            "target_platform": "OTT",
            "localization_mode": "multilingual_dub",
            "marketing_budget": "high",
            "target_languages": ["Hindi", "Tamil", "Telugu", "Bengali"],
            "target_states": ["Maharashtra", "Karnataka", "Tamil Nadu", "Telangana"],
        },
    )
    assert response.status_code == 201, response.text
    result = response.json()["result"]
    assert result["score_delta"] > 0
    assert result["cost_level"] == "high"
    assert result["reach_level"] == "high"
    assert result["recommendation"]["localization"]
