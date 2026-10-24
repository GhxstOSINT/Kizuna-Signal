from datetime import date, datetime

from sqlalchemy import ARRAY, Date, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TitleAssumption(Base):
    """Release assumptions for a title (one set per title; updated in place)."""

    __tablename__ = "title_assumptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    title_id: Mapped[int] = mapped_column(
        ForeignKey("titles.id", ondelete="CASCADE"), unique=True
    )
    distribution_model: Mapped[str] = mapped_column(String(32))
    localization_mode: Mapped[str] = mapped_column(String(32))
    languages: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    launch_geography: Mapped[str] = mapped_column(String(32))
    target_states: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    planned_launch_date: Mapped[date | None] = mapped_column(Date)
    marketing_budget_band: Mapped[str | None] = mapped_column(String(16))
    positioning: Mapped[str | None] = mapped_column(String(32))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
