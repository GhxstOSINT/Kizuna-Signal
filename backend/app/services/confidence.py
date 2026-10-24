from __future__ import annotations

import statistics

from app.db.models import Title
from app.schemas.analysis import ComparableTitle
from app.services.scoring import WEIGHTS
from app.services.sources.base import SourceEvidence


def clamp(value: float) -> float:
    return round(max(0, min(100, value)), 2)


def calculate_confidence(
    title: Title,
    evidence: list[SourceEvidence],
    comparables: list[ComparableTitle],
    unmeasured: set[str] | None = None,
) -> tuple[float, str, list[str]]:
    required = [
        title.name,
        title.synopsis,
        title.content_format,
        title.primary_genre,
        title.source_material,
        title.expected_release_period,
    ]
    completeness = sum(bool(item) for item in required) / len(required)
    available = [item for item in evidence if item.status != "unavailable"]
    source_coverage = len(available) / max(1, len(evidence))
    # Components with no evidence at all weigh on confidence in proportion to their score weight.
    measured_weight = 1 - sum(WEIGHTS[key] for key in (unmeasured or set()))
    coverage = 0.5 * source_coverage + 0.5 * measured_weight
    freshness = statistics.mean([item.freshness_score for item in available]) if available else 0
    quality = statistics.mean([item.quality_score for item in available]) if available else 0
    comparable_quality = (
        statistics.mean([item.similarity for item in comparables]) if comparables else 0
    )

    score = 100 * (
        0.20 * completeness
        + 0.25 * coverage
        + 0.15 * freshness
        + 0.20 * quality
        + 0.20 * comparable_quality
    )
    warnings: list[str] = []
    for item in evidence:
        warnings.extend(item.warnings)
    if unmeasured:
        warnings.append(
            "Not measured, so excluded from the score: "
            + ", ".join(sorted(key.replace("_", " ") for key in unmeasured))
            + "."
        )
    if source_coverage < 1:
        missing = [item.source for item in evidence if item.status == "unavailable"]
        warnings.append(f"Analysis completed without: {', '.join(missing)}.")
    if not title.target_languages:
        warnings.append(
            "No localization language was supplied; regional recommendations use inferred defaults."
        )
    if len(title.themes) < 2:
        warnings.append("Limited theme metadata reduces comparable-title specificity.")

    # Demand and engagement are the only components that evidence this particular title's
    # traction; without them the result rests on priors and must read as low confidence.
    traction = ("demand_momentum", "engagement_quality")
    traction_total = sum(WEIGHTS[key] for key in traction)
    traction_share = 1 - sum(WEIGHTS[key] for key in traction if key in (unmeasured or set())) / (
        traction_total
    )
    score *= 0.5 + 0.5 * traction_share
    if traction_share == 0:
        warnings.append(
            "No title-specific demand or engagement evidence was found; the score reflects "
            "content fit and genre benchmarks only."
        )

    final_score = clamp(score)
    level = "high" if final_score >= 75 else "medium" if final_score >= 50 else "low"
    return final_score, level, list(dict.fromkeys(warnings))


def confidence_interval(market_score: float, confidence: float) -> tuple[float, float]:
    half_width = 4 + (100 - confidence) * 0.12
    return (
        round(max(0, market_score - half_width), 2),
        round(min(100, market_score + half_width), 2),
    )
