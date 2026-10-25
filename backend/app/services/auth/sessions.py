from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import AuthSession, OAuthAccount, User, utcnow
from app.services.auth.oauth import Profile

COOKIE = "kizuna_session"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def upsert_user(db: Session, profile: Profile) -> User:
    """Find or create the user behind a provider identity.

    A second provider joins an existing user only when both report the same *verified* email,
    so signing in with Google and GitHub as the same person lands on one portfolio.
    """
    account = db.scalar(
        select(OAuthAccount).where(
            OAuthAccount.provider == profile.provider,
            OAuthAccount.provider_user_id == profile.subject,
        )
    )
    email = profile.email.lower() if profile.email_verified and profile.email else None
    if account:
        user = account.user
    else:
        user = db.scalar(select(User).where(User.email == email)) if email else None
        if user is None:
            user = User(name=profile.name, email=email, avatar_url=profile.avatar_url)
            db.add(user)
        user.accounts.append(
            OAuthAccount(provider=profile.provider, provider_user_id=profile.subject)
        )
    if user.email is None and email:
        user.email = email
    user.name = profile.name or user.name
    user.avatar_url = profile.avatar_url or user.avatar_url
    user.last_login_at = utcnow()
    db.commit()
    db.refresh(user)
    return user


def create_session(db: Session, user: User, ttl_days: int) -> str:
    token = secrets.token_urlsafe(32)
    now = utcnow()
    db.add(
        AuthSession(
            token_hash=_hash(token), user_id=user.id, expires_at=now + timedelta(days=ttl_days)
        )
    )
    db.execute(delete(AuthSession).where(AuthSession.expires_at < now))
    db.commit()
    return token


def user_for_token(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    session = db.get(AuthSession, _hash(token))
    if session is None:
        return None
    expires_at = session.expires_at
    if expires_at.tzinfo is None:  # SQLite drops the timezone
        expires_at = expires_at.replace(tzinfo=utcnow().tzinfo)
    if expires_at < utcnow():
        return None
    return db.get(User, session.user_id)


def end_session(db: Session, token: str | None) -> None:
    if token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == _hash(token)))
        db.commit()
