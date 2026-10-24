from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_serializer


def utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class ProjectCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=2, max_length=160)
    organization_name: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=2000)


class ProjectRead(ProjectCreate):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True, extra="forbid")

    id: str
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return utc_iso(value)


class TitleCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=240)
    english_title: str | None = Field(default=None, max_length=240)
    synopsis: str = Field(min_length=40, max_length=12000)
    content_format: str = Field(min_length=2, max_length=80)
    primary_genre: str = Field(min_length=2, max_length=80)
    genres: list[str] = Field(default_factory=list, max_length=12)
    themes: list[str] = Field(default_factory=list, max_length=20)
    source_material: str = Field(min_length=2, max_length=80)
    expected_release_period: str = Field(min_length=2, max_length=80)
    target_platform: str = Field(default="undecided", max_length=80)
    target_languages: list[str] = Field(default_factory=list, max_length=12)
    target_states: list[str] = Field(default_factory=list, max_length=20)
    marketing_budget: str = Field(default="medium", pattern="^(low|medium|high)$")
    studio: str | None = Field(default=None, max_length=160)
    franchise_status: str | None = Field(default=None, max_length=80)
    trailer_url: HttpUrl | None = None
    metadata_extra: dict = Field(default_factory=dict)


class TitleRead(TitleCreate):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True, extra="forbid")

    id: str
    project_id: str
    trailer_url: str | None = None
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return utc_iso(value)
