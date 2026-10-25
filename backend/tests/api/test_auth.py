from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.core.config import get_settings
from app.db.models import AuthSession, OAuthAccount, User
from app.db.session import SessionLocal
from app.services.auth import oauth, sessions
from app.services.auth.oauth import OAuthError, Profile


@pytest.fixture
def configured(monkeypatch):
    settings = get_settings()
    for name in (
        "google_client_id",
        "google_client_secret",
        "github_client_id",
        "github_client_secret",
    ):
        monkeypatch.setattr(settings, name, "set")
    return settings


def profile(provider="google", subject="g-1", email="ada@example.com", verified=True, name="Ada"):
    return Profile(provider, subject, name, email, verified, "https://img.example/a.png")


def start_login(client, provider):
    response = client.get(f"/api/v1/auth/{provider}/login", follow_redirects=False)
    state = parse_qs(urlparse(response.headers["location"]).query)["state"][0]
    return response, state


def finish_login(client, monkeypatch, who, provider="google", state=None):
    monkeypatch.setattr(oauth, "fetch_profile", lambda *_: who)
    if state is None:
        _, state = start_login(client, provider)
    return client.get(
        f"/api/v1/auth/{provider}/callback",
        params={"code": "abc", "state": state},
        follow_redirects=False,
    )


@pytest.mark.api
def test_providers_report_which_are_configured(anonymous_client, configured, monkeypatch):
    monkeypatch.setattr(configured, "github_client_secret", "")
    rows = anonymous_client.get("/api/v1/auth/providers").json()["providers"]
    assert {row["id"]: row["enabled"] for row in rows} == {"google": True, "github": False}


@pytest.mark.api
@pytest.mark.parametrize(
    "provider,host", [("google", "accounts.google.com"), ("github", "github.com")]
)
def test_login_redirects_to_the_provider_with_state(anonymous_client, configured, provider, host):
    response, state = start_login(anonymous_client, provider)
    target = urlparse(response.headers["location"])
    query = parse_qs(target.query)
    assert response.status_code == 302 and target.netloc == host
    assert query["redirect_uri"] == [f"http://localhost:4173/api/v1/auth/{provider}/callback"]
    assert f"{provider}.{state}" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]


@pytest.mark.api
def test_login_without_credentials_returns_to_the_login_page(anonymous_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "google_client_id", "")
    response = anonymous_client.get("/api/v1/auth/google/login", follow_redirects=False)
    assert response.headers["location"].endswith("/login?error=not_configured")


@pytest.mark.api
def test_unknown_provider_is_404(anonymous_client):
    assert anonymous_client.get("/api/v1/auth/myspace/login").status_code == 404
    assert anonymous_client.get("/api/v1/auth/myspace/callback").status_code == 404


@pytest.mark.api
def test_callback_signs_in_and_sets_a_session_cookie(anonymous_client, configured, monkeypatch):
    response = finish_login(anonymous_client, monkeypatch, profile())
    assert response.status_code == 302 and response.headers["location"] == "http://localhost:4173/"
    assert "kizuna_session=" in response.headers["set-cookie"]
    me = anonymous_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "ada@example.com" and me.json()["name"] == "Ada"


@pytest.mark.security
def test_callback_rejects_a_state_that_does_not_match(anonymous_client, configured, monkeypatch):
    start_login(anonymous_client, "google")
    response = finish_login(anonymous_client, monkeypatch, profile(), state="forged")
    assert response.headers["location"].endswith("/login?error=state")
    assert anonymous_client.get("/api/v1/auth/me").status_code == 401


@pytest.mark.security
def test_callback_without_the_state_cookie_is_rejected(anonymous_client, configured, monkeypatch):
    monkeypatch.setattr(oauth, "fetch_profile", lambda *_: profile())
    response = anonymous_client.get(
        "/api/v1/auth/google/callback", params={"code": "x", "state": "y"}, follow_redirects=False
    )
    assert response.headers["location"].endswith("/login?error=state")


@pytest.mark.security
def test_state_from_one_provider_does_not_work_for_another(
    anonymous_client, configured, monkeypatch
):
    _, state = start_login(anonymous_client, "google")
    response = finish_login(anonymous_client, monkeypatch, profile("github"), "github", state)
    assert response.headers["location"].endswith("/login?error=state")


@pytest.mark.api
def test_user_denying_access_returns_to_the_login_page(anonymous_client, configured):
    _, state = start_login(anonymous_client, "github")
    response = anonymous_client.get(
        "/api/v1/auth/github/callback",
        params={"error": "access_denied", "state": state},
        follow_redirects=False,
    )
    assert response.headers["location"].endswith("/login?error=denied")


@pytest.mark.api
def test_provider_failure_returns_to_the_login_page(anonymous_client, configured, monkeypatch):
    def boom(*_):
        raise OAuthError("down")

    monkeypatch.setattr(oauth, "fetch_profile", boom)
    _, state = start_login(anonymous_client, "google")
    response = anonymous_client.get(
        "/api/v1/auth/google/callback", params={"code": "x", "state": state}, follow_redirects=False
    )
    assert response.headers["location"].endswith("/login?error=provider")


@pytest.mark.api
def test_logout_ends_the_session(client):
    assert client.get("/api/v1/auth/me").status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    with SessionLocal() as db:
        assert db.query(AuthSession).count() == 0


@pytest.mark.security
def test_project_routes_require_sign_in(anonymous_client):
    for method, path in [
        ("get", "/api/v1/projects"),
        ("post", "/api/v1/projects"),
        ("get", "/api/v1/titles/x"),
        ("get", "/api/v1/analyses/x"),
        ("delete", "/api/v1/analyses/x"),
        ("get", "/api/v1/jobs/x"),
    ]:
        response = getattr(anonymous_client, method)(path)
        assert response.status_code == 401, path
        assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.security
def test_forged_and_expired_sessions_are_rejected(anonymous_client, client):
    anonymous_client.cookies.set("kizuna_session", "not-a-real-token")
    assert anonymous_client.get("/api/v1/projects").status_code == 401
    with SessionLocal() as db:
        user = db.query(User).one()
        token = sessions.create_session(db, user, ttl_days=-1)
        assert sessions.user_for_token(db, token) is None
        assert sessions.user_for_token(db, None) is None


@pytest.mark.security
def test_session_token_is_stored_hashed(client):
    token = client.cookies.get("kizuna_session")
    with SessionLocal() as db:
        assert db.get(AuthSession, token) is None
        assert db.query(AuthSession).one().token_hash == sessions._hash(token)


@pytest.mark.api
def test_same_provider_identity_is_the_same_user(anonymous_client, configured, monkeypatch):
    finish_login(anonymous_client, monkeypatch, profile(name="Ada"))
    finish_login(anonymous_client, monkeypatch, profile(name="Ada Lovelace"))
    with SessionLocal() as db:
        assert db.query(User).count() == 1
        assert db.query(User).one().name == "Ada Lovelace"


@pytest.mark.api
def test_github_and_google_share_a_user_by_verified_email(
    anonymous_client, configured, monkeypatch
):
    finish_login(anonymous_client, monkeypatch, profile("google", "g-1", "Ada@Example.com"))
    finish_login(
        anonymous_client, monkeypatch, profile("github", "42", "ada@example.com"), "github"
    )
    with SessionLocal() as db:
        assert db.query(User).count() == 1
        assert db.query(OAuthAccount).count() == 2


@pytest.mark.security
def test_unverified_email_never_links_accounts(anonymous_client, configured, monkeypatch):
    finish_login(anonymous_client, monkeypatch, profile("google", "g-1", "ada@example.com"))
    finish_login(
        anonymous_client,
        monkeypatch,
        profile("github", "42", "ada@example.com", verified=False),
        "github",
    )
    with SessionLocal() as db:
        assert db.query(User).count() == 2
        assert db.query(User).filter(User.email.is_(None)).count() == 1


# --- provider handshake, against a fake Google/GitHub ---------------------------------------


def fake_providers(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(oauth, "_http", lambda: httpx.Client(transport=transport))


def google_handler(request):
    if request.url.host == "oauth2.googleapis.com":
        assert b"code=abc" in request.content
        return httpx.Response(200, json={"access_token": "tok"})
    assert request.headers["authorization"] == "Bearer tok"
    return httpx.Response(
        200,
        json={"sub": "1", "email": "a@b.co", "email_verified": True, "name": "A", "picture": "p"},
    )


def github_handler(emails):
    def handler(request):
        if request.url.host == "github.com":
            return httpx.Response(200, json={"access_token": "tok"})
        if request.url.path == "/user/emails":
            return httpx.Response(200, json=emails) if emails is not None else httpx.Response(404)
        return httpx.Response(
            200, json={"id": 7, "login": "ada-gh", "name": None, "avatar_url": "a"}
        )

    return handler


@pytest.mark.adapters
def test_google_profile(monkeypatch, configured):
    fake_providers(monkeypatch, google_handler)
    got = oauth.fetch_profile(configured, "google", "abc")
    assert (got.subject, got.email, got.email_verified, got.name) == ("1", "a@b.co", True, "A")


@pytest.mark.adapters
def test_github_profile_uses_the_primary_verified_email(monkeypatch, configured):
    emails = [
        {"email": "old@x.io", "primary": False, "verified": True},
        {"email": "main@x.io", "primary": True, "verified": True},
    ]
    fake_providers(monkeypatch, github_handler(emails))
    got = oauth.fetch_profile(configured, "github", "abc")
    assert (got.subject, got.email, got.email_verified, got.name) == (
        "7",
        "main@x.io",
        True,
        "ada-gh",
    )


@pytest.mark.adapters
@pytest.mark.parametrize("emails", [None, [{"email": "x@y.z", "primary": True, "verified": False}]])
def test_github_profile_without_a_verified_email(monkeypatch, configured, emails):
    fake_providers(monkeypatch, github_handler(emails))
    got = oauth.fetch_profile(configured, "github", "abc")
    assert got.email is None and got.email_verified is False


@pytest.mark.adapters
def test_handshake_failures_become_oauth_errors(monkeypatch, configured):
    fake_providers(monkeypatch, lambda request: httpx.Response(500))
    with pytest.raises(OAuthError):
        oauth.fetch_profile(configured, "google", "abc")
    fake_providers(monkeypatch, lambda request: httpx.Response(200, json={"error": "bad_code"}))
    with pytest.raises(OAuthError):
        oauth.fetch_profile(configured, "github", "abc")
    fake_providers(monkeypatch, lambda request: httpx.Response(200, text="<html>"))
    with pytest.raises(OAuthError):
        oauth.fetch_profile(configured, "google", "abc")
