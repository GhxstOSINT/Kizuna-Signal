from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.analysis import LaunchRecommendation


class ScenarioCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    target_platform: str | None = Field(default=None, max_length=80)
    localization_mode: str | None = Field(
        default=None,
        pattern="^(subtitles|dub|multilingual_dub)$",
    )
    marketing_budget: str | None = Field(default=None, pattern="^(low|medium|high)$")
    target_states: list[str] | None = Field(default=None, max_length=20)
    target_languages: list[str] | None = Field(default=None, max_length=12)
    disabled_sources: list[str] = Field(default_factory=list)


class ScenarioResult(BaseModel):
    base_score: float
    scenario_score: float
    score_delta: float
    base_confidence: float
    scenario_confidence: float
    confidence_delta: float
    cost_level: str
    reach_level: str
    recommendation: LaunchRecommendation
    applied_overrides: dict


class ScenarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    analysis_id: str
    name: str
    overrides: dict
    result: ScenarioResult
