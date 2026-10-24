def test_liveness(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_exposes_versions(client):
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["model_status"] == "ready"
    assert payload["model_version"].startswith("state-lift-")
    assert payload["scoring_version"].startswith("market-potential-")
