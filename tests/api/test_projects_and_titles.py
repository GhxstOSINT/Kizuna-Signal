from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parents[1] / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.api
def test_golden_project_and_title_round_trip(client):
    project = client.post("/api/v1/projects", json=load_fixture("golden_project.json"))
    assert project.status_code == 201
    project_payload = project.json()
    assert project_payload["created_at"].endswith("Z")

    title = client.post(
        f"/api/v1/projects/{project_payload['id']}/titles",
        json=load_fixture("golden_title.json"),
    )
    assert title.status_code == 201
    title_payload = title.json()
    assert title_payload["name"] == "架空の物語"
    assert title_payload["project_id"] == project_payload["id"]
    assert title_payload["created_at"].endswith("Z")

    projects = client.get("/api/v1/projects").json()
    titles = client.get(f"/api/v1/projects/{project_payload['id']}/titles").json()
    assert any(item["id"] == project_payload["id"] for item in projects)
    assert any(item["id"] == title_payload["id"] for item in titles)


@pytest.mark.api
@pytest.mark.parametrize("length,expected", [(39, 422), (40, 201)])
def test_synopsis_boundary(client, title_payload, length, expected):
    project = client.post("/api/v1/projects", json={"name": "Boundary"}).json()
    title_payload["synopsis"] = "x" * length
    response = client.post(
        f"/api/v1/projects/{project['id']}/titles",
        json=title_payload,
    )
    assert response.status_code == expected


@pytest.mark.api
def test_unknown_fields_and_wrong_types_are_rejected(client, title_payload):
    project = client.post("/api/v1/projects", json={"name": "Strict Contract"}).json()
    title_payload["unexpected_field"] = "not permitted"
    extra = client.post(f"/api/v1/projects/{project['id']}/titles", json=title_payload)
    assert extra.status_code == 422

    title_payload.pop("unexpected_field")
    title_payload["themes"] = {"wrong": "type"}
    wrong_type = client.post(f"/api/v1/projects/{project['id']}/titles", json=title_payload)
    assert wrong_type.status_code == 422
