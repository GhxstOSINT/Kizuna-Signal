from __future__ import annotations

import hmac
import logging
import secrets

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.config import Settings, get_settings
from app.db.models import User
from app.db.session import get_db
from app.schemas.auth import ProviderRead, ProvidersRead, UserRead
from app.services.auth import oauth, sessions

router = APIRouter()
log = logging.getLogger(__name__)

STATE_COOKIE = "kizuna_oauth_state"
STATE_SECONDS = 600


def _secure(settings: Settings) -> bool:
    return settings.public_url.startswith("https://")


def _login_page(settings: Settings, error: str | None = None) -> RedirectResponse:
    base = settings.public_url.rstrip("/")
    return RedirectResponse(f"{base}/login?error={error}" if error else f"{base}/", status_code=302)


def _state_path(settings: Settings) -> str:
    return f"{settings.api_v1_prefix}/auth"


@router.get("/providers", response_model=ProvidersRead)
def list_providers(settings: Settings = Depends(get_settings)) -> ProvidersRead:
    return ProvidersRead(
        providers=[
            ProviderRead(
                id=spec.id, label=spec.label, enabled=oauth.is_configured(settings, spec.id)
            )
            for spec in oauth.PROVIDERS.values()
        ]
    )


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(current_user)) -> User:
    return user


@router.post("/logout", status_code=204)
def logout(
    token: str | None = Cookie(default=None, alias=sessions.COOKIE),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    sessions.end_session(db, token)
    response = Response(status_code=204)
    response.delete_cookie(
        sessions.COOKIE, path="/", secure=_secure(settings), httponly=True, samesite="lax"
    )
    return response


@router.get("/{provider}/login", include_in_schema=False)
def login(provider: str, settings: Settings = Depends(get_settings)) -> RedirectResponse:
    """Send the browser to Google or GitHub. Used as a plain link, so failures redirect back."""
    if provider not in oauth.PROVIDERS:
        raise HTTPException(status_code=404, detail="Unknown sign-in provider")
    if not oauth.is_configured(settings, provider):
        return _login_page(settings, "not_configured")
    state = secrets.token_urlsafe(24)
    response = RedirectResponse(oauth.authorize_url(settings, provider, state), status_code=302)
    response.set_cookie(
        STATE_COOKIE,
        f"{provider}.{state}",
        max_age=STATE_SECONDS,
        path=_state_path(settings),
        httponly=True,
        samesite="lax",
        secure=_secure(settings),
    )
    return response


@router.get("/{provider}/callback", include_in_schema=False)
def callback(
    provider: str,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    saved_state: str | None = Cookie(default=None, alias=STATE_COOKIE),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    if provider not in oauth.PROVIDERS:
        raise HTTPException(status_code=404, detail="Unknown sign-in provider")

    def finish(response: RedirectResponse) -> RedirectResponse:
        response.delete_cookie(STATE_COOKIE, path=_state_path(settings))
        return response

    # The state must match the cookie set by /login: it ties the callback to this browser.
    expected = f"{provider}.{state}" if state else ""
    if not saved_state or not hmac.compare_digest(saved_state, expected):
        return finish(_login_page(settings, "state"))
    if error or not code:
        return finish(_login_page(settings, "denied"))
    try:
        profile = oauth.fetch_profile(settings, provider, code)
    except oauth.OAuthError as exc:
        log.warning("sign-in failed: %s", exc)
        return finish(_login_page(settings, "provider"))

    user = sessions.upsert_user(db, profile)
    token = sessions.create_session(db, user, settings.session_ttl_days)
    response = finish(_login_page(settings))
    response.set_cookie(
        sessions.COOKIE,
        token,
        max_age=settings.session_ttl_days * 86400,
        path="/",
        httponly=True,
        samesite="lax",
        secure=_secure(settings),
    )
    return response
