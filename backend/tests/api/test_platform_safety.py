from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError

from app.api.routes.health import readiness


class BrokenSession:
    def execute(self, _):
        raise OperationalError("SELECT 1", {}, Exception("database unavailable"))


@pytest.mark.chaos
def test_readiness_fails_cleanly_when_database_is_unavailable():
    response = readiness(BrokenSession())
    assert response.status_code == 503
    assert b"database unavailable" not in response.body
    assert b'"database":"unavailable"' in response.body


@pytest.mark.security
def test_health_endpoints_do_not_expose_secrets(client):
    for path in ("/health/live", "/api/v1/health/ready", "/api/v1/sources/health"):
        response = client.get(path)
        text = response.text.lower()
        assert response.status_code == 200
        assert "password" not in text
        assert "api_key" not in text
        assert "token" not in text
        assert "traceback" not in text


@pytest.mark.security
def test_cors_allows_configured_origin_only(client):
    allowed = client.options(
        "/api/v1/projects",
        headers={
            "origin": "http://localhost:3000",
            "access-control-request-method": "POST",
        },
    )
    blocked = client.options(
        "/api/v1/projects",
        headers={
            "origin": "https://attacker.invalid",
            "access-control-request-method": "POST",
        },
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert blocked.headers.get("access-control-allow-origin") is None


@pytest.mark.api
def test_non_browser_client_is_not_blocked_by_cors(client):
    response = client.get("/api/v1/projects")
    assert response.status_code == 200
