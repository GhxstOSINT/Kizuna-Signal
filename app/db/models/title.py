from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Title(Base):
    __tablename__ = "titles"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name_en: Mapped[str] = mapped_column(String(255), index=True)
    name_jp: Mapped[str | None] = mapped_column(String(255))
    synopsis: Mapped[str | None] = mapped_column(Text)
    genres: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    format: Mapped[str | None] = mapped_column(String(50))
    studio: Mapped[str | None] = mapped_column(String(255))
    cast_members: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    franchise: Mapped[str | None] = mapped_column(String(255))
    release_date: Mapped[date | None] = mapped_column(Date)
    is_unreleased: Mapped[bool] = mapped_column(default=True)
    embedding = mapped_column(Vector(384), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
