from __future__ import annotations

import pytest


def assert_error_shape(response, expected_code: str) -> None:
    payload = response.json()
    assert set(payload) == {"error"}
    assert payload["error"]["code"] == expected_code
    assert isinstance(payload["error"]["message"], str)
    assert isinstance(payload["error"]["details"], list)
    assert isinstance(payload["error"]["warnings"], list)


@pytest.mark.contract
def test_not_found_uses_unified_error_shape(client):
    response = client.get("/api/v1/projects/missing")
    assert response.status_code == 404
    assert_error_shape(response, "not_found")


@pytest.mark.contract
def test_validation_uses_unified_error_shape(client):
    response = client.post("/api/v1/projects", json={"name": " "})
    assert response.status_code == 422
    assert_error_shape(response, "validation_error")
    assert response.json()["error"]["details"][0]["field"] == "name"


@pytest.mark.contract
def test_unknown_route_and_wrong_method_are_structured(client):
    missing = client.get("/api/v1/nonexistent")
    wrong_method = client.delete("/api/v1/projects")
    assert missing.status_code == 404
    assert_error_shape(missing, "not_found")
    assert wrong_method.status_code == 405
    assert_error_shape(wrong_method, "method_not_allowed")


@pytest.mark.contract
def test_malformed_json_is_controlled(client):
    response = client.post(
        "/api/v1/projects",
        content=b'{"name":',
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422
    assert_error_shape(response, "validation_error")
