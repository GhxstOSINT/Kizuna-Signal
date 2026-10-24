from __future__ import annotations

from app.db.models import Title
from app.schemas.analysis import AnalysisResult
from app.schemas.scenario import ScenarioCreate, ScenarioResult
from app.services.recommendations import build_recommendation


def clamp(value: float) -> float:
    return round(max(0, min(100, value)), 2)


def run_scenario(title: Title, base: AnalysisResult, request: ScenarioCreate) -> ScenarioResult:
    score_delta = 0.0
    confidence_delta = 0.0

    if request.localization_mode == "multilingual_dub":
        score_delta += 5.5
        confidence_delta -= 1.5
    elif request.localization_mode == "dub":
        score_delta += 3.0
    elif request.localization_mode == "subtitles":
        score_delta += 0.5

    if request.marketing_budget == "high":
        score_delta += 2.5
    elif request.marketing_budget == "low":
        score_delta -= 2.0

    if request.target_languages:
        score_delta += min(4.0, len(request.target_languages) * 0.9)
    if request.target_states:
        strong_states = {item.state for item in base.regional_scores[:5]}
        aligned = len(strong_states & set(request.target_states))
        score_delta += min(3.0, aligned * 0.8)

    if request.target_platform and request.target_platform.lower() == "ott":
        score_delta += 1.5

    if request.disabled_sources:
        confidence_delta -= 7.0 * len(request.disabled_sources)
        score_delta -= 1.0 * len(request.disabled_sources)

    scenario_score = clamp(base.market_potential_score + score_delta)
    scenario_confidence = clamp(base.confidence_score + confidence_delta)
    platform = request.target_platform or title.target_platform

    original_platform = title.target_platform
    original_languages = list(title.target_languages)
    try:
        title.target_platform = platform
        if request.target_languages is not None:
            title.target_languages = request.target_languages
        recommendation = build_recommendation(
            title,
            scenario_score,
            scenario_confidence,
            base.regional_scores,
            request.localization_mode,
        )
    finally:
        title.target_platform = original_platform
        title.target_languages = original_languages

    budget = request.marketing_budget or title.marketing_budget
    cost_level = (
        "high"
        if request.localization_mode == "multilingual_dub" or budget == "high"
        else "medium"
        if budget == "medium" or request.localization_mode == "dub"
        else "low"
    )
    reach_level = (
        "high" if len(request.target_languages or title.target_languages) >= 3 else "moderate"
    )

    overrides = request.model_dump(exclude_none=True)
    return ScenarioResult(
        base_score=base.market_potential_score,
        scenario_score=scenario_score,
        score_delta=round(scenario_score - base.market_potential_score, 2),
        base_confidence=base.confidence_score,
        scenario_confidence=scenario_confidence,
        confidence_delta=round(scenario_confidence - base.confidence_score, 2),
        cost_level=cost_level,
        reach_level=reach_level,
        recommendation=recommendation,
        applied_overrides=overrides,
    )
