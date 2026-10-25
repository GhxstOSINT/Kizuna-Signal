from __future__ import annotations

from app.core.config import get_settings
from app.db.models import Title
from app.schemas.analysis import AnalysisResult
from app.schemas.scenario import ScenarioCreate, ScenarioResult
from app.services.confidence import calculate_confidence
from app.services.recommendations import build_recommendation
from app.services.scoring import (
    calculate_component_scores,
    calculate_market_score,
    unmeasured_components,
)
from app.services.sources.base import SourceEvidence
from app.services.sources.regional_context import RegionalContextAdapter
from app.services.survey import SurveyData

TITLE_COLUMNS = (
    "name",
    "english_title",
    "synopsis",
    "content_format",
    "primary_genre",
    "genres",
    "themes",
    "source_material",
    "expected_release_period",
    "target_platform",
    "target_languages",
    "target_states",
    "marketing_budget",
    "studio",
    "franchise_status",
    "trailer_url",
)


def clamp(value: float) -> float:
    return round(max(0, min(100, value)), 2)


def _variant(title: Title, request: ScenarioCreate | None) -> Title:
    """A transient copy of the title (never persisted) with the scenario's overrides applied."""
    copy = Title(**{column: getattr(title, column) for column in TITLE_COLUMNS})
    if request is None:
        return copy
    if request.target_platform:
        copy.target_platform = request.target_platform
    if request.target_languages is not None:
        copy.target_languages = request.target_languages
    if request.target_states is not None:
        copy.target_states = request.target_states
    if request.marketing_budget:
        copy.marketing_budget = request.marketing_budget
    return copy


def evidence_from_snapshot(snapshot: dict, disabled: set[str]) -> list[SourceEvidence]:
    """Rebuild the measured evidence stored with an analysis (sources in `disabled` go dark)."""
    evidence = []
    for source, item in snapshot.items():
        if source in disabled:
            evidence.append(
                SourceEvidence(
                    source,
                    "unavailable",
                    0.0,
                    0.0,
                    warnings=[f"{source} was disabled for this scenario."],
                )
            )
            continue
        evidence.append(
            SourceEvidence(
                source=source,
                status=item["status"],
                freshness_score=item["freshness_score"],
                quality_score=item["quality_score"],
                metrics=dict(item.get("metrics", {})),
                warnings=list(item.get("warnings", [])),
                provenance=dict(item.get("provenance", {})),
                regional={k: dict(v) for k, v in item.get("regional", {}).items()},
            )
        )
    return evidence


def _measure(
    variant: Title, evidence: list[SourceEvidence], base: AnalysisResult
) -> tuple[float, float]:
    """Deterministic score and confidence for a title variant from the stored evidence.

    Regional context (Census language coverage, addressable market, survey affinity) is the one
    source that depends on the plan, so it is recomputed for the variant; every other source keeps
    the value measured at analysis time.
    """
    settings = get_settings()
    refreshed = []
    for item in evidence:
        if item.source == "regional_context" and item.status != "unavailable":
            refreshed.append(
                RegionalContextAdapter(SurveyData.from_dir(settings.survey_dir)).collect(variant)
            )
        else:
            refreshed.append(item)
    comparables = base.comparable_titles
    components = calculate_component_scores(variant, refreshed, comparables)
    unmeasured = unmeasured_components(variant, refreshed, comparables)
    score = calculate_market_score(components, unmeasured)
    confidence, _, _ = calculate_confidence(variant, refreshed, comparables, unmeasured)
    return score, confidence


def run_scenario(
    title: Title,
    base: AnalysisResult,
    request: ScenarioCreate,
    snapshot: dict | None = None,
) -> ScenarioResult:
    """Score a changed launch plan as the base result plus the measured effect of the change.

    The effect is the difference between two runs of the evidence-based scoring formulas: one for
    the original plan and one for the scenario, both on the evidence stored with the analysis.
    Target languages and states move the score through Census coverage; disabling a source moves
    score and confidence through the missing evidence. Platform, budget and localization mode have
    no measured effect on demand, so they change cost, reach and the written plan but not the score.
    A scenario with no changes therefore reproduces the base score.
    """
    scenario_title = _variant(title, request)
    if snapshot:
        disabled = set(request.disabled_sources)
        base_score, base_conf = _measure(
            _variant(title, None), evidence_from_snapshot(snapshot, set()), base
        )
        new_score, new_conf = _measure(
            scenario_title, evidence_from_snapshot(snapshot, disabled), base
        )
        scenario_score = clamp(base.market_potential_score + (new_score - base_score))
        scenario_confidence = clamp(base.confidence_score + (new_conf - base_conf))
    else:  # analyses without a stored snapshot cannot be re-measured
        scenario_score, scenario_confidence = base.market_potential_score, base.confidence_score

    recommendation = build_recommendation(
        scenario_title,
        scenario_score,
        scenario_confidence,
        base.regional_scores,
        request.localization_mode,
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
