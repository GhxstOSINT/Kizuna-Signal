from __future__ import annotations

from app.db.models import Title
from app.schemas.analysis import AnalysisResult
from app.schemas.scenario import ScenarioCreate, ScenarioResult
from app.services.comparables import find_comparables
from app.services.confidence import calculate_confidence
from app.services.recommendations import build_recommendation
from app.services.scoring import (
    calculate_component_scores,
    calculate_market_score,
    calculate_regional_scores,
)
from app.services.sources.base import SourceEvidence
from app.services.sources.live import RegionalContextCensus

TITLE_COLUMNS = (
    "name", "english_title", "synopsis", "content_format", "primary_genre", "genres", "themes",
    "source_material", "expected_release_period", "target_platform", "target_languages",
    "target_states", "marketing_budget", "studio", "franchise_status", "trailer_url",
)


def clamp(value: float) -> float:
    return round(max(0, min(100, value)), 2)


def _scenario_title(title: Title, request: ScenarioCreate) -> Title:
    """A transient copy of the title with the scenario's overrides applied (never persisted)."""
    copy = Title(**{column: getattr(title, column) for column in TITLE_COLUMNS})
    if request.target_platform:
        copy.target_platform = request.target_platform
    if request.target_languages is not None:
        copy.target_languages = request.target_languages
    if request.target_states is not None:
        copy.target_states = request.target_states
    if request.marketing_budget:
        copy.marketing_budget = request.marketing_budget
    return copy


def _evidence(base: AnalysisResult, scenario_title: Title, disabled: set[str]) -> list[SourceEvidence]:
    """The base analysis' measured evidence, with regional context recomputed for the overrides."""
    evidence = []
    for item in base.source_status:
        if item.source in disabled:
            evidence.append(
                SourceEvidence(item.source, "unavailable", 0.0, 0.0,
                               warnings=[f"{item.source} was disabled for this scenario."])
            )
        elif item.source == "regional_context":
            evidence.append(RegionalContextCensus().collect(scenario_title))
        else:
            evidence.append(
                SourceEvidence(item.source, item.status, item.freshness_score, item.quality_score,
                               dict(item.metrics), list(item.warnings), dict(item.provenance))
            )
    return evidence


def run_scenario(
    title: Title,
    base: AnalysisResult,
    request: ScenarioCreate,
    partner_index: dict[str, float] | None = None,
) -> ScenarioResult:
    """Recompute the full score for the scenario from the stored evidence and the changed inputs.

    Platform, budget, languages and states flow through the real scoring and regional model.
    Localization mode has no measured effect on demand, so it changes cost, reach and the plan
    but not the score.
    """
    scenario_title = _scenario_title(title, request)
    evidence = _evidence(base, scenario_title, set(request.disabled_sources))
    comparables = find_comparables(scenario_title)
    components = calculate_component_scores(scenario_title, evidence, comparables)
    scenario_score = calculate_market_score(components)
    scenario_confidence, _, _ = calculate_confidence(scenario_title, evidence, comparables)
    regions = calculate_regional_scores(
        scenario_title, scenario_score, scenario_confidence, evidence, partner_index
    )
    recommendation = build_recommendation(
        scenario_title, scenario_score, scenario_confidence, regions, request.localization_mode
    )

    budget = scenario_title.marketing_budget
    cost_level = (
        "high"
        if request.localization_mode == "multilingual_dub" or budget == "high"
        else "medium"
        if budget == "medium" or request.localization_mode == "dub"
        else "low"
    )
    reach_level = "high" if len(scenario_title.target_languages) >= 3 else "moderate"

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
        applied_overrides=request.model_dump(exclude_none=True),
    )
