from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.sources import KNOWN_SOURCES
from app.schemas.common import CleanList, iso_language_codes
from app.schemas.enums import (
    BudgetBand,
    DistributionModel,
    JobStatus,
    JobType,
    LaunchGeography,
    LocalizationMode,
    Positioning,
    RecommendationCategory,
    RegionType,
    ReportFormat,
    SourceHealth,
)


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- jobs --------------------------------------------------------------------
class JobOut(ORM):
    id: int
    job_type: JobType
    status: JobStatus
    result: dict[str, Any] | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


# --- sources -----------------------------------------------------------------
def _check_sources(names: list[str] | None) -> list[str] | None:
    if names is None:
        return names
    unknown = sorted(set(names) - set(KNOWN_SOURCES))
    if unknown:
        raise ValueError(f"unknown sources: {', '.join(unknown)}")
    return list(dict.fromkeys(names))


class SourceOut(ORM):
    name: str
    enabled: bool
    health: SourceHealth
    last_collected_at: datetime | None
    last_error: str | None


class SourceUpdate(BaseModel):
    enabled: bool


class CollectRequest(BaseModel):
    title_id: int = Field(gt=0)
    sources: list[str] | None = Field(
        default=None, description="Defaults to every enabled source"
    )

    _sources = field_validator("sources")(_check_sources)


class SourceRunOut(ORM):
    id: int
    source_id: int
    title_id: int
    job_id: int | None
    health: SourceHealth
    record_count: int
    from_cache: bool
    raw_checksum: str | None
    warnings: list[str]
    collected_at: datetime


# --- analyses ----------------------------------------------------------------
class AnalysisOut(ORM):
    """Carries result version, confidence, provenance summary and warning codes."""

    id: int
    title_id: int
    job_id: int | None
    status: JobStatus
    result_version: str | None
    market_potential: float | None
    confidence: float | None
    warning_codes: list[str]
    provenance_summary: dict[str, Any]
    disabled_sources: list[str]
    created_at: datetime
    completed_at: datetime | None


class RegionalScoreOut(ORM):
    region_type: RegionType
    region_code: str
    region_name: str
    score: float
    confidence: float | None
    rank: int
    evidence: list[Any]


# --- scenarios ---------------------------------------------------------------
class ScenarioOverrides(BaseModel):
    """Only these levers may be overridden; anything else is rejected."""

    model_config = ConfigDict(extra="forbid")

    localization_mode: LocalizationMode | None = None
    languages: CleanList | None = None
    distribution_model: DistributionModel | None = None
    launch_geography: LaunchGeography | None = None
    target_states: CleanList | None = None
    planned_launch_date: date | None = None
    marketing_budget_band: BudgetBand | None = None
    positioning: Positioning | None = None
    disabled_sources: list[str] | None = None
    excluded_comparable_ids: list[int] | None = None

    _sources = field_validator("disabled_sources")(_check_sources)

    @field_validator("languages")
    @classmethod
    def _languages(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else iso_language_codes(value)

    @model_validator(mode="after")
    def check(self) -> "ScenarioOverrides":
        if not self.model_dump(exclude_none=True):
            raise ValueError("at least one override is required")
        if self.launch_geography == LaunchGeography.NATIONAL and self.target_states:
            raise ValueError("target_states must be empty for a national launch")
        return self


class ScenarioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    overrides: ScenarioOverrides


class ScenarioOut(ORM):
    id: int
    analysis_id: int
    job_id: int | None
    name: str
    overrides: dict[str, Any]
    status: JobStatus
    score_delta: float | None
    confidence_delta: float | None
    cost_delta: float | None
    created_at: datetime


# --- recommendations ---------------------------------------------------------
class RecommendationOut(ORM):
    id: int
    analysis_id: int
    category: RecommendationCategory
    decision: str
    expected_benefit: str
    evidence: list[Any]
    confidence: float
    principal_risk: str
    status: Literal["draft", "accepted", "rejected"]
    decided_by: str | None
    decided_at: datetime | None


class RecommendationDecision(BaseModel):
    """Human approval is required before a recommendation counts as accepted."""

    status: Literal["accepted", "rejected"]
    decided_by: str = Field(min_length=1, max_length=255)


# --- reports -----------------------------------------------------------------
class ReportCreate(BaseModel):
    analysis_id: int = Field(gt=0)
    format: ReportFormat = ReportFormat.PDF


class ReportOut(ORM):
    id: int
    analysis_id: int
    job_id: int | None
    format: ReportFormat
    status: JobStatus
    file_uri: str | None
    created_at: datetime
