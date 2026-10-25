from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Only a provider-verified address is stored, so it is safe to match accounts on it.
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(160))
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    accounts: Mapped[list[OAuthAccount]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    projects: Mapped[list[Project]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class OAuthAccount(Base):
    """One sign-in identity (a Google or GitHub account) belonging to a user."""

    __tablename__ = "oauth_accounts"
    __table_args__ = (UniqueConstraint("provider", "provider_user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    provider_user_id: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="accounts")


class AuthSession(Base):
    """A signed-in browser. Only the SHA-256 of the cookie token is stored."""

    __tablename__ = "auth_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Null only for rows created before sign-in existed; nobody can see those.
    owner_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(160), index=True)
    organization_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    owner: Mapped[User | None] = relationship(back_populates="projects")
    titles: Mapped[list[Title]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Title(Base):
    __tablename__ = "titles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(240), index=True)
    english_title: Mapped[str | None] = mapped_column(String(240), nullable=True)
    synopsis: Mapped[str] = mapped_column(Text)
    content_format: Mapped[str] = mapped_column(String(80))
    primary_genre: Mapped[str] = mapped_column(String(80))
    genres: Mapped[list[str]] = mapped_column(JSON, default=list)
    themes: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_material: Mapped[str] = mapped_column(String(80))
    expected_release_period: Mapped[str] = mapped_column(String(80))
    target_platform: Mapped[str] = mapped_column(String(80), default="undecided")
    target_languages: Mapped[list[str]] = mapped_column(JSON, default=list)
    target_states: Mapped[list[str]] = mapped_column(JSON, default=list)
    marketing_budget: Mapped[str] = mapped_column(String(40), default="medium")
    studio: Mapped[str | None] = mapped_column(String(160), nullable=True)
    franchise_status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    trailer_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    director: Mapped[str | None] = mapped_column(String(160), nullable=True)
    episode_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    age_rating: Mapped[str | None] = mapped_column(String(40), nullable=True)
    target_audience: Mapped[str | None] = mapped_column(String(80), nullable=True)
    metadata_extra: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped[Project] = relationship(back_populates="titles")
    analyses: Mapped[list[Analysis]] = relationship(
        back_populates="title", cascade="all, delete-orphan"
    )


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title_id: Mapped[str] = mapped_column(ForeignKey("titles.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="queued", index=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    model_version: Mapped[str] = mapped_column(String(120))
    feature_version: Mapped[str] = mapped_column(String(120))
    scoring_version: Mapped[str] = mapped_column(String(120))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    title: Mapped[Title] = relationship(back_populates="analyses")
    scenarios: Mapped[list[Scenario]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
    job: Mapped[Job | None] = relationship(
        back_populates="analysis", uselist=False, cascade="all, delete-orphan"
    )


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    overrides: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    analysis: Mapped[Analysis] = relationship(back_populates="scenarios")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"), unique=True
    )
    status: Mapped[str] = mapped_column(String(40), default="queued", index=True)
    progress: Mapped[int] = mapped_column(default=0)
    stage: Mapped[str] = mapped_column(String(160), default="queued")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    analysis: Mapped[Analysis] = relationship(back_populates="job")
