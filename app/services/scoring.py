from __future__ import annotations

import statistics

from app.db.models import Title
from app.schemas.analysis import ComparableTitle, PredictionDriver, RegionalScore
from app.services.sources.base import SourceEvidence

WEIGHTS = {
    "content_fit": 0.25,
    "demand_momentum": 0.25,
    "regional_opportunity": 0.20,
    "engagement_quality": 0.15,
    "comparable_performance": 0.15,
}

STATE_PROFILES = {
    "Maharashtra": {"base": 84, "language": "Hindi", "platform": "OTT"},
    "Karnataka": {"base": 81, "language": "Kannada", "platform": "OTT"},
    "Delhi NCR": {"base": 80, "language": "Hindi", "platform": "OTT"},
    "Tamil Nadu": {"base": 79, "language": "Tamil", "platform": "OTT"},
    "Telangana": {"base": 77, "language": "Telugu", "platform": "OTT"},
    "West Bengal": {"base": 73, "language": "Bengali", "platform": "OTT"},
    "Kerala": {"base": 72, "language": "Malayalam", "platform": "OTT"},
    "Uttar Pradesh": {"base": 70, "language": "Hindi", "platform": "OTT"},
}


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return round(max(low, min(high, value)), 2)


def metric(evidence: list[SourceEvidence], source: str, key: str, default: float = 50) -> float:
    item = next(
        (entry for entry in evidence if entry.source == source and entry.status != "unavailable"),
        None,
    )
    return float(item.metrics.get(key, default)) if item else default


def calculate_component_scores(
    title: Title,
    evidence: list[SourceEvidence],
    comparables: list[ComparableTitle],
) -> dict[str, float]:
    completeness = (
        sum(
            bool(value)
            for value in [
                title.synopsis,
                title.content_format,
                title.primary_genre,
                title.source_material,
                title.expected_release_period,
                title.genres,
                title.themes,
            ]
        )
        / 7
    )
    content_fit = 55 + completeness * 22
    if title.primary_genre.lower() in {"action", "fantasy", "romance", "thriller", "comedy"}:
        content_fit += 7
    if title.target_languages:
        content_fit += min(6, len(title.target_languages) * 1.5)

    demand_momentum = statistics.mean(
        [
            metric(evidence, "google_trends", "relative_interest"),
            metric(evidence, "google_trends", "momentum"),
            metric(evidence, "wikimedia", "curiosity"),
        ]
    )
    engagement_quality = statistics.mean(
        [
            metric(evidence, "youtube", "attention"),
            metric(evidence, "youtube", "engagement_quality"),
            metric(evidence, "youtube", "velocity"),
        ]
    )
    regional_opportunity = statistics.mean(
        [
            metric(evidence, "regional_context", "language_fit"),
            metric(evidence, "regional_context", "addressable_market"),
        ]
    )
    comparable_performance = (
        statistics.mean(
            [item.market_signal * (0.65 + 0.35 * item.similarity) for item in comparables]
        )
        if comparables
        else 50
    )

    return {
        "content_fit": clamp(content_fit),
        "demand_momentum": clamp(demand_momentum),
        "regional_opportunity": clamp(regional_opportunity),
        "engagement_quality": clamp(engagement_quality),
        "comparable_performance": clamp(comparable_performance),
    }


def calculate_market_score(components: dict[str, float]) -> float:
    return clamp(sum(components[key] * weight for key, weight in WEIGHTS.items()))


def decision_classification(score: float, confidence: float) -> str:
    if confidence < 45:
        return "insufficient_evidence"
    if score >= 80:
        return "strong_opportunity"
    if score >= 68:
        return "promising_opportunity"
    if score >= 55:
        return "test_before_investing"
    return "limited_opportunity"


def calculate_regional_scores(
    title: Title,
    market_score: float,
    confidence: float,
) -> list[RegionalScore]:
    selected_languages = {item.lower() for item in title.target_languages}
    selected_states = set(title.target_states)
    rows: list[RegionalScore] = []
    for state, profile in STATE_PROFILES.items():
        language_match = 5 if profile["language"].lower() in selected_languages else 0
        target_match = 4 if state in selected_states else 0
        platform_match = 2 if title.target_platform.lower() in {"ott", "undecided"} else 0
        score = clamp(
            0.58 * market_score
            + 0.42 * profile["base"]
            + language_match
            + target_match
            + platform_match
        )
        state_confidence = clamp(
            confidence
            - (3 if state not in {"Maharashtra", "Karnataka", "Delhi NCR", "Tamil Nadu"} else 0)
        )
        reasons = [
            f"Regional baseline indicates {profile['language']} audience opportunity.",
            f"Title-level potential contributes {market_score:.1f}/100 to this region.",
        ]
        if language_match:
            reasons.append(f"The proposed localization includes {profile['language']}.")
        rows.append(
            RegionalScore(
                state=state,
                score=score,
                confidence=state_confidence,
                recommended_language=profile["language"],
                preferred_platform=profile["platform"],
                reasons=reasons,
            )
        )
    return sorted(rows, key=lambda row: row.score, reverse=True)


def build_drivers(
    components: dict[str, float],
    title: Title,
    evidence: list[SourceEvidence],
) -> tuple[list[PredictionDriver], list[PredictionDriver]]:
    positives: list[PredictionDriver] = []
    negatives: list[PredictionDriver] = []
    labels = {
        "content_fit": "Content-India fit",
        "demand_momentum": "Demand momentum",
        "regional_opportunity": "Regional opportunity",
        "engagement_quality": "Engagement quality",
        "comparable_performance": "Comparable performance",
    }
    for key, value in sorted(components.items(), key=lambda item: item[1], reverse=True):
        contribution = round((value - 60) * WEIGHTS[key] / 2, 2)
        driver = PredictionDriver(
            name=labels[key],
            contribution=abs(contribution),
            direction="positive" if contribution >= 0 else "negative",
            evidence=f"Component score {value:.1f}/100 under scoring version market-potential-0.1.0.",
        )
        (positives if contribution >= 0 else negatives).append(driver)

    if not title.target_languages:
        negatives.append(
            PredictionDriver(
                name="Localization plan not specified",
                contribution=2.5,
                direction="negative",
                evidence="No target Indian language was provided in the title assumptions.",
            )
        )
    unavailable = [item.source for item in evidence if item.status == "unavailable"]
    if unavailable:
        negatives.append(
            PredictionDriver(
                name="Incomplete public evidence",
                contribution=round(1.8 * len(unavailable), 2),
                direction="negative",
                evidence=f"Unavailable sources: {', '.join(unavailable)}.",
            )
        )

    return positives[:5], negatives[:5]
