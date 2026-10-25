from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.core.config import Settings


class OAuthError(Exception):
    """The provider refused the sign-in or could not be reached."""


@dataclass(frozen=True)
class Profile:
    provider: str
    subject: str
    name: str
    email: str | None
    email_verified: bool
    avatar_url: str | None


@dataclass(frozen=True)
class Provider:
    id: str
    label: str
    authorize_url: str
    token_url: str
    scope: str


PROVIDERS: dict[str, Provider] = {
    "google": Provider(
        "google",
        "Google",
        "https://accounts.google.com/o/oauth2/v2/auth",
        "https://oauth2.googleapis.com/token",
        "openid email profile",
    ),
    "github": Provider(
        "github",
        "GitHub",
        "https://github.com/login/oauth/authorize",
        "https://github.com/login/oauth/access_token",
        "read:user user:email",
    ),
}

GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


def credentials(settings: Settings, provider: str) -> tuple[str, str]:
    return getattr(settings, f"{provider}_client_id"), getattr(
        settings, f"{provider}_client_secret"
    )


def is_configured(settings: Settings, provider: str) -> bool:
    return all(credentials(settings, provider))


def redirect_uri(settings: Settings, provider: str) -> str:
    return f"{settings.public_url.rstrip('/')}{settings.api_v1_prefix}/auth/{provider}/callback"


def authorize_url(settings: Settings, provider: str, state: str) -> str:
    spec = PROVIDERS[provider]
    params = {
        "client_id": credentials(settings, provider)[0],
        "redirect_uri": redirect_uri(settings, provider),
        "scope": spec.scope,
        "state": state,
        "response_type": "code",
    }
    if provider == "google":
        params["prompt"] = "select_account"
    return f"{spec.authorize_url}?{urlencode(params)}"


def _http() -> httpx.Client:
    return httpx.Client(timeout=10.0, headers={"User-Agent": "KizunaSignal"})


def fetch_profile(settings: Settings, provider: str, code: str) -> Profile:
    """Trade the one-time code for the provider's view of who just signed in."""
    try:
        with _http() as client:
            token = _exchange_code(client, settings, provider, code)
            if provider == "google":
                return _google_profile(client, token)
            return _github_profile(client, token)
    except httpx.HTTPError as exc:
        raise OAuthError(f"{provider} could not be reached") from exc
    except (ValueError, KeyError) as exc:
        raise OAuthError(f"{provider} returned an unexpected response") from exc


def _exchange_code(client: httpx.Client, settings: Settings, provider: str, code: str) -> str:
    client_id, client_secret = credentials(settings, provider)
    response = client.post(
        PROVIDERS[provider].token_url,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri(settings, provider),
            "grant_type": "authorization_code",
        },
        headers={"Accept": "application/json"},
    )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise OAuthError(f"{provider} did not grant access")
    return token


def _google_profile(client: httpx.Client, token: str) -> Profile:
    response = client.get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {token}"})
    response.raise_for_status()
    data = response.json()
    email = data.get("email")
    return Profile(
        provider="google",
        subject=str(data["sub"]),
        name=data.get("name") or (email or "Google user").split("@")[0],
        email=email,
        email_verified=bool(email and data.get("email_verified")),
        avatar_url=data.get("picture"),
    )


def _github_profile(client: httpx.Client, token: str) -> Profile:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    response = client.get(GITHUB_USER_URL, headers=headers)
    response.raise_for_status()
    data = response.json()
    email, verified = None, False
    # /user shows only the public address; the primary one needs the user:email scope.
    emails = client.get(GITHUB_EMAILS_URL, headers=headers)
    if emails.status_code == 200:
        primary = next(
            (row for row in emails.json() if row.get("primary") and row.get("verified")), None
        )
        if primary:
            email, verified = primary["email"], True
    return Profile(
        provider="github",
        subject=str(data["id"]),
        name=data.get("name") or data["login"],
        email=email,
        email_verified=verified,
        avatar_url=data.get("avatar_url"),
    )
