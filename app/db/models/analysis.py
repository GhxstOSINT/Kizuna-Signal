from datetime import datetime

from sqlalchemy import (
    ARRAY,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Analysis(Base):
    """One scored run for a title. Result columns stay null until the worker fills them."""

    __tablename__ = "analyses"
    __table_args__ = (UniqueConstraint("title_id", "idempotency_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title_id: Mapped[int] = mapped_column(ForeignKey("titles.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    result_version: Mapped[str | None] = mapped_column(String(32))  # scoring config version
    market_potential: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    warning_codes: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    provenance_summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    disabled_sources: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RegionalScore(Base):
    __tablename__ = "regional_scores"
    __table_args__ = (UniqueConstraint("analysis_id", "region_type", "region_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"), index=True
    )
    region_type: Mapped[str] = mapped_column(String(16))  # state | language
    region_code: Mapped[str] = mapped_column(String(32))
    region_name: Mapped[str] = mapped_column(String(128))
    score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    rank: Mapped[int] = mapped_column(Integer)
    evidence: Mapped[list] = mapped_column(JSONB, default=list)
