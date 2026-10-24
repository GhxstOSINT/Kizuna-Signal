from __future__ import annotations

import statistics

from app.db.models import Title
from app.schemas.analysis import ComparableTitle
from app.services.sources.base import SourceEvidence


def clamp(value: float) -> float:
    return round(max(0, min(100, value)), 2)


def calculate_confidence(
    title: Title,
    evidence: list[SourceEvidence],
    comparables: list[ComparableTitle],
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
    coverage = len(available) / max(1, len(evidence))
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
    if coverage < 1:
        missing = [item.source for item in evidence if item.status == "unavailable"]
        warnings.append(f"Analysis completed without: {', '.join(missing)}.")
    if not title.target_languages:
        warnings.append(
            "No localization language was supplied; regional recommendations use inferred defaults."
        )
    if len(title.themes) < 2:
        warnings.append("Limited theme metadata reduces comparable-title specificity.")

    final_score = clamp(score)
    level = "high" if final_score >= 75 else "medium" if final_score >= 50 else "low"
    return final_score, level, list(dict.fromkeys(warnings))


def confidence_interval(market_score: float, confidence: float) -> tuple[float, float]:
    half_width = 4 + (100 - confidence) * 0.12
    return (
        round(max(0, market_score - half_width), 2),
        round(min(100, market_score + half_width), 2),
    )
