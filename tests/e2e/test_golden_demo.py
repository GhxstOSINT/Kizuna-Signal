from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.mark.e2e
@pytest.mark.demo
def test_golden_demo_is_deterministic(client):
    project_body = json.loads((FIXTURES / "golden_project.json").read_text(encoding="utf-8"))
    title_body = json.loads((FIXTURES / "golden_title.json").read_text(encoding="utf-8"))

    project = client.post("/api/v1/projects", json=project_body).json()
    title = client.post(f"/api/v1/projects/{project['id']}/titles", json=title_body).json()

    first = client.post(f"/api/v1/titles/{title['id']}/analyses").json()
    second = client.post(f"/api/v1/titles/{title['id']}/analyses").json()
    first_result = client.get(f"/api/v1/analyses/{first['analysis_id']}/result").json()
    second_result = client.get(f"/api/v1/analyses/{second['analysis_id']}/result").json()

    ignored = {"analysis_id"}
    assert {k: v for k, v in first_result.items() if k not in ignored} == {
        k: v for k, v in second_result.items() if k not in ignored
    }
    assert first_result["market_potential_score"] == second_result["market_potential_score"]
    assert len(first_result["comparable_titles"]) == 5
    assert first_result["recommendation"]["priority_markets"]


@pytest.mark.e2e
@pytest.mark.demo
def test_golden_partial_source_demo(client):
    project_body = json.loads((FIXTURES / "golden_project.json").read_text(encoding="utf-8"))
    title_body = json.loads((FIXTURES / "golden_title.json").read_text(encoding="utf-8"))
    project = client.post("/api/v1/projects", json=project_body).json()
    title = client.post(f"/api/v1/projects/{project['id']}/titles", json=title_body).json()

    complete = client.post(f"/api/v1/titles/{title['id']}/analyses").json()
    partial = client.post(
        f"/api/v1/titles/{title['id']}/analyses",
        json={"disabled_sources": ["youtube"]},
    ).json()
    complete_result = client.get(f"/api/v1/analyses/{complete['analysis_id']}/result").json()
    partial_analysis = client.get(f"/api/v1/analyses/{partial['analysis_id']}").json()

    assert partial_analysis["status"] == "partially_completed"
    assert partial_analysis["result"]["confidence_score"] < complete_result["confidence_score"]
    assert partial_analysis["result"]["negative_drivers"]
