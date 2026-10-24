from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.schemas.project import utc_iso

AnalysisStatus = Literal["queued", "running", "completed", "partially_completed", "failed"]
DecisionClassification = Literal[
    "strong_opportunity",
    "promising_opportunity",
    "test_before_investing",
    "limited_opportunity",
    "insufficient_evidence",
]


class SourceStatus(BaseModel):
    source: str
    status: Literal["available", "cached", "unavailable"]
    freshness_score: float = Field(ge=0, le=1)
    quality_score: float = Field(ge=0, le=1)
    metrics: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    provenance: dict[str, str] = Field(default_factory=dict)


class ComparableTitle(BaseModel):
    title: str
    similarity: float = Field(ge=0, le=1)
    market_signal: float = Field(ge=0, le=100)
    reasons: list[str]


class PredictionDriver(BaseModel):
    name: str
    contribution: float
    direction: Literal["positive", "negative"]
    evidence: str


class RegionalScore(BaseModel):
    state: str
    score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=100)
    recommended_language: str
    preferred_platform: str
    reasons: list[str]


class LaunchRecommendation(BaseModel):
    decision: str
    platform: str
    priority_markets: list[str]
    localization: list[str]
    target_audience: list[str]
    launch_window: str
    marketing_positioning: str
    campaign_actions: list[str]
    risks: list[str]


class AnalysisResult(BaseModel):
    analysis_id: str
    title_id: str
    market_potential_score: float = Field(ge=0, le=100)
    decision_classification: DecisionClassification
    confidence_score: float = Field(ge=0, le=100)
    confidence_level: Literal["low", "medium", "high"]
    confidence_interval: tuple[float, float]
    component_scores: dict[str, float]
    regional_scores: list[RegionalScore]
    comparable_titles: list[ComparableTitle]
    positive_drivers: list[PredictionDriver]
    negative_drivers: list[PredictionDriver]
    source_status: list[SourceStatus]
    data_quality_warnings: list[str]
    recommendation: LaunchRecommendation
    model_version: str
    feature_version: str
    scoring_version: str
    score_origin: Literal["trained_model", "deterministic_fallback"] = "deterministic_fallback"
    score_meaning: str = "A bounded relative market-opportunity index, not a revenue forecast."
    model_warnings: list[str] = Field(default_factory=list)
    component_details: list[dict] = Field(default_factory=list)
    model_evaluation: dict = Field(default_factory=dict)


class AnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title_id: str
    status: AnalysisStatus
    result: AnalysisResult | None
    warnings: list[str]
    model_version: str
    feature_version: str
    scoring_version: str
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    @field_serializer("created_at", "completed_at")
    def serialize_timestamps(self, value: datetime | None) -> str | None:
        return utc_iso(value) if value is not None else None


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    analysis_id: str
    status: AnalysisStatus
    progress: int
    stage: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_timestamps(self, value: datetime) -> str:
        return utc_iso(value)


class AnalysisCreated(BaseModel):
    analysis_id: str
    job_id: str
    status: AnalysisStatus


class SourceToggleRequest(BaseModel):
    disabled_sources: list[str] = Field(default_factory=list)
