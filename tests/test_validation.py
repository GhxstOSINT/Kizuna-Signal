def test_title_requires_meaningful_synopsis(client):
    project = client.post("/api/v1/projects", json={"name": "Validation"}).json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/titles",
        json={
            "name": "Too Short",
            "synopsis": "Short",
            "content_format": "film",
            "primary_genre": "drama",
            "source_material": "original",
            "expected_release_period": "2027",
        },
    )
    assert response.status_code == 422


def test_unknown_resources_return_404(client):
    assert client.get("/api/v1/projects/missing").status_code == 404
    assert client.get("/api/v1/analyses/missing").status_code == 404
    assert client.get("/api/v1/jobs/missing").status_code == 404
