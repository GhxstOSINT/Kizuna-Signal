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
    assert result["score_origin"] == "trained_model"
    assert result["model_version"].startswith("state-lift-")
    assert result["component_details"]
    assert result["model_evaluation"]["oof_titles"]


def test_analysis_discloses_deterministic_fallback(client, created_title, monkeypatch):
    def missing_model(title, evidence_confidence):
        raise FileNotFoundError("model intentionally unavailable")

    monkeypatch.setattr("app.services.analysis.score_title", missing_model)
    analysis = start_and_read_analysis(client, created_title["id"])
    result = analysis["result"]
    assert result["score_origin"] == "deterministic_fallback"
    assert any("fallback" in warning.lower() for warning in result["model_warnings"])


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


def test_failed_analysis_does_not_leak_exception_details(client, created_title, monkeypatch):
    secret = "INSERT INTO internal_table VALUES ('s3cr3t') failed at /srv/app/db.py"

    def explode(self, title, disabled_sources=None):
        raise RuntimeError(secret)

    monkeypatch.setattr("app.services.analysis.SourceRegistry.collect", explode)
    started = client.post(f"/api/v1/titles/{created_title['id']}/analyses", json=None)
    assert started.status_code == 202, started.text
    identifiers = started.json()

    job = client.get(f"/api/v1/jobs/{identifiers['job_id']}").json()
    analysis = client.get(f"/api/v1/analyses/{identifiers['analysis_id']}").json()
    assert job["status"] == "failed"
    assert analysis["status"] == "failed"
    for payload in (job, analysis):
        assert payload["error_message"]
        assert "s3cr3t" not in str(payload)
        assert "internal_table" not in str(payload)
