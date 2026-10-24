from __future__ import annotations

import math
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


def metric(evidence: list[SourceEvidence], source: str, key: str) -> float | None:
    """A source's metric, or None when the source is unavailable or did not report it."""
    item = next(
        (entry for entry in evidence if entry.source == source and entry.status != "unavailable"),
        None,
    )
    if item is None or key not in item.metrics:
        return None
    return float(item.metrics[key])


def _mean(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return statistics.mean(present) if present else None


def _components(
    title: Title,
    evidence: list[SourceEvidence],
    comparables: list[ComparableTitle],
) -> dict[str, float | None]:
    """Component scores, with None for a component that has no evidence at all."""
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
    survey_genre = metric(evidence, "regional_context", "genre_affinity")
    if survey_genre is not None:  # measured viewer preference outweighs the genre heuristic
        content_fit = 0.65 * content_fit + 0.35 * survey_genre

    comparable_performance = (
        statistics.mean(
            [item.market_signal * (0.65 + 0.35 * item.similarity) for item in comparables]
        )
        if comparables
        else None
    )
    return {
        "content_fit": clamp(content_fit),
        "demand_momentum": _mean(
            [
                metric(evidence, "google_trends", "relative_interest"),
                metric(evidence, "google_trends", "momentum"),
                metric(evidence, "wikimedia", "curiosity"),
            ]
        ),
        "regional_opportunity": _mean(
            [
                metric(evidence, "regional_context", "language_fit"),
                metric(evidence, "regional_context", "addressable_market"),
                survey_genre,
            ]
        ),
        "engagement_quality": _mean(
            [
                metric(evidence, "youtube", "attention"),
                metric(evidence, "youtube", "engagement_quality"),
                metric(evidence, "youtube", "velocity"),
                metric(evidence, "anilist", "community_strength"),
            ]
        ),
        "comparable_performance": comparable_performance,
    }


def calculate_component_scores(
    title: Title,
    evidence: list[SourceEvidence],
    comparables: list[ComparableTitle],
) -> dict[str, float]:
    """All five components; an unmeasured one is reported as a neutral 50 (see unmeasured_*)."""
    return {
        key: clamp(value if value is not None else 50)
        for key, value in _components(title, evidence, comparables).items()
    }


def unmeasured_components(
    title: Title,
    evidence: list[SourceEvidence],
    comparables: list[ComparableTitle],
) -> set[str]:
    return {
        key for key, value in _components(title, evidence, comparables).items() if value is None
    }


def calculate_market_score(
    components: dict[str, float], unmeasured: set[str] | None = None
) -> float:
    """Weighted score over measured components, regressed toward neutral when evidence is thin.

    Weights are renormalised over the measured components so a missing source is not scored as
    a neutral 50. The result is then shrunk toward 50 by sqrt(measured weight share): with only
    the "prior" components (content fit, localization plan, comparables) the estimate must not
    look as certain as one backed by demand and engagement evidence.
    """
    measured = {key: weight for key, weight in WEIGHTS.items() if key not in (unmeasured or set())}
    total = sum(measured.values())
    if not total:
        return 50.0
    renormalised = sum(components[key] * weight for key, weight in measured.items()) / total
    shrink = math.sqrt(total / sum(WEIGHTS.values()))
    return clamp(50 + (renormalised - 50) * shrink)


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
    unmeasured: set[str] | None = None,
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
        if key in (unmeasured or set()):
            continue
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
