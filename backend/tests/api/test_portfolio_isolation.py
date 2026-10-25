from __future__ import annotations

import pytest


@pytest.fixture
def owned(client, title_payload):
    project = client.post("/api/v1/projects", json={"name": "Mine"}).json()
    title = client.post(f"/api/v1/projects/{project['id']}/titles", json=title_payload).json()
    analysis_id = client.post(f"/api/v1/titles/{title['id']}/analyses", json={}).json()
    return project, title, analysis_id


@pytest.mark.security
def test_each_person_sees_only_their_own_portfolio(client, other_client, owned):
    project, title, _ = owned
    assert [p["id"] for p in client.get("/api/v1/projects").json()] == [project["id"]]
    assert other_client.get("/api/v1/projects").json() == []
    assert client.get(f"/api/v1/projects/{project['id']}/titles").json()[0]["id"] == title["id"]


@pytest.mark.security
def test_other_peoples_records_look_missing(client, other_client, owned, title_payload):
    project, title, created = owned
    analysis_id, job_id = created["analysis_id"], created["job_id"]
    result_before = client.get(f"/api/v1/analyses/{analysis_id}/result")
    reads = [
        f"/api/v1/projects/{project['id']}",
        f"/api/v1/projects/{project['id']}/titles",
        f"/api/v1/titles/{title['id']}",
        f"/api/v1/titles/{title['id']}/analyses",
        f"/api/v1/analyses/{analysis_id}",
        f"/api/v1/analyses/{analysis_id}/result",
        f"/api/v1/analyses/{analysis_id}/scenarios",
        f"/api/v1/jobs/{job_id}",
    ]
    for path in reads:
        assert other_client.get(path).status_code == 404, path
    assert other_client.post(f"/api/v1/titles/{title['id']}/analyses", json={}).status_code == 404
    assert (
        other_client.post(
            f"/api/v1/projects/{project['id']}/titles", json=title_payload
        ).status_code
        == 404
    )
    assert (
        other_client.post(
            f"/api/v1/analyses/{analysis_id}/scenarios", json={"name": "Dub plan"}
        ).status_code
        == 404
    )
    assert other_client.delete(f"/api/v1/analyses/{analysis_id}").status_code == 404
    # untouched for the owner
    assert client.get(f"/api/v1/analyses/{analysis_id}").status_code == 200
    assert (
        client.get(f"/api/v1/analyses/{analysis_id}/result").status_code
        == result_before.status_code
    )


@pytest.mark.api
def test_new_projects_belong_to_the_creator(client, other_client):
    client.post("/api/v1/projects", json={"name": "Ada's slate"})
    other_client.post("/api/v1/projects", json={"name": "Bob's slate"})
    assert [p["name"] for p in client.get("/api/v1/projects").json()] == ["Ada's slate"]
    assert [p["name"] for p in other_client.get("/api/v1/projects").json()] == ["Bob's slate"]
