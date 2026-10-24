"""Canonical title record used by the ML pipeline (one row per title)."""

from datetime import date

from pydantic import BaseModel, Field


class TitleRecord(BaseModel):
    title_id: str  # "anilist:<id>"
    franchise_id: str  # root of the PREQUEL chain when known, else title_id
    media_type: str = "anime"
    original_title: str | None = None
    english_title: str | None = None
    japanese_title: str | None = None
    romanized_title: str | None = None
    indian_language_aliases: list[str] = Field(default_factory=list)
    source_ids: dict[str, str | int] = Field(default_factory=dict)
    genres: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    format: str | None = None
    runtime_or_episode_count: dict[str, int | None] = Field(default_factory=dict)
    original_release_date: date | None = None
    india_release_date: date | None = None
    india_release_date_evidence: str | None = None  # source/URL, or None when unknown
    localization_languages: list[str] = Field(default_factory=list)
    platform_or_distributor: list[str] = Field(default_factory=list)
    synopsis: str | None = None  # input to Content DNA embeddings

    def anchor_date(self) -> date | None:
        """Release date that anchors Trends windows: India date if evidenced, else original."""
        if self.india_release_date and self.india_release_date_evidence:
            return self.india_release_date
        return self.original_release_date
