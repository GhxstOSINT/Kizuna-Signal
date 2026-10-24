from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import CleanList, iso_language_codes
from app.schemas.enums import ContentFormat, LocalizationMode

MIN_SYNOPSIS_CHARS = 50


class PredictIn(BaseModel):
    """Everything needed for a one-shot prediction. No project, title row or job is created."""

    name_en: str = Field(min_length=1, max_length=255, examples=["Blade of Dawn"])
    name_jp: str | None = Field(default=None, max_length=255)
    genres: CleanList = Field(min_length=1, examples=[["Action", "Fantasy"]])
    tags: CleanList = Field(default=[], description="AniList-style tags, e.g. 'Male Protagonist'")
    synopsis: str = Field(min_length=MIN_SYNOPSIS_CHARS, description="Used to find similar past titles")
    format: ContentFormat = ContentFormat.ANIME_SERIES
    studio: str | None = Field(default=None, max_length=255)
    release_date: date | None = Field(default=None, description="Planned launch; defaults to today")
    episodes: int | None = Field(default=None, gt=0)
    minutes_per_episode: float | None = Field(default=None, gt=0)
    languages: CleanList = []
    localization_mode: LocalizationMode | None = None
    include_seo: bool = Field(default=False, description="Also measure search terms on Google Trends (slow, live)")

    _languages = field_validator("languages")(lambda v: iso_language_codes(v) if v else v)


class StateResult(BaseModel):
    rank: int
    state: str
    name: str
    lift: float = Field(description="log scale; >0 means expected to over-perform vs a typical anime there")
    low: float
    high: float
    expected_share: float = Field(description="predicted share of India demand; sums to 1 across states")
    train_titles: int
    drivers: list[dict[str, Any]]


class IndiaSummary(BaseModel):
    confidence: float = Field(ge=0, le=100)
    confidence_factors: dict[str, float]
    warnings: list[str]
    top_states: list[str]
    bottom_states: list[str]
    note: str


class PredictOut(BaseModel):
    model_version: str
    task: str
    title: str
    india: IndiaSummary
    states: list[StateResult]
    comparables: list[dict[str, Any]]
    seo: dict[str, Any] | None = None
