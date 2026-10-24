from __future__ import annotations

import math
import statistics

from app.db.models import Title
from app.schemas.analysis import RegionalScore
from app.services import census
from app.services.sources.base import SourceEvidence
from app.services.textmatch import normalise

# Signal weights for a state's composite; absent signals are dropped and the rest renormalised.
WEIGHTS = {"demand": 0.35, "size": 0.20, "urban": 0.10, "targeting": 0.15, "survey": 0.20}
TITLE_ANCHOR = 0.45  # share of a state's score taken from the title-level market score
SMALL_STATE = 5_000_000
SHRINK_POPULATION = 10_000_000  # Trends is noisy below this; interest is shrunk toward the median
NOT_TARGETED = 35.0


def has_regional_evidence(evidence: list[SourceEvidence]) -> bool:
    """True when real Census/Trends/survey data (not the offline demo) is available."""
    return any(
        item.status != "unavailable"
        and (item.regional or item.provenance.get("mode") == "static-census")
        for item in evidence
    )


def _regional(evidence: list[SourceEvidence], source: str) -> dict[str, dict[str, float]]:
    item = next((e for e in evidence if e.source == source and e.status != "unavailable"), None)
    return item.regional if item else {}


def calculate_regional_scores_live(
    title: Title,
    market_score: float,
    confidence: float,
    evidence: list[SourceEvidence],
) -> list[RegionalScore]:
    """State scores from Census size/urbanisation, Trends interest by state and survey affinity."""
    states = census.all_states()
    trends = _regional(evidence, "google_trends")
    survey = _regional(evidence, "regional_context")
    targeted_languages = {normalise(language) for language in title.target_languages}
    targeted_states = {
        state.name for state in map(census.resolve_state, title.target_states) if state
    }
    has_targets = bool(targeted_languages or targeted_states)
    max_population = max(state.population for state in states.values())
    median_interest = statistics.median(v["interest"] for v in trends.values()) if trends else None
    platform = "OTT" if title.target_platform.lower() == "undecided" else title.target_platform

    rows: list[RegionalScore] = []
    for name, state in states.items():
        signals: dict[str, float] = {
            "size": 100 * math.sqrt(state.population / max_population),
            "urban": state.urban_pct,
        }
        reasons = [
            f"Population {state.population / 1e6:.1f}M and {state.urban_pct:.0f}% urban "
            f"(Census {census.CENSUS_YEAR})."
        ]
        state_confidence = confidence

        if name in trends and median_interest is not None:
            raw = trends[name]["interest"]
            weight = min(1.0, math.sqrt(state.population / SHRINK_POPULATION))
            signals["demand"] = median_interest + (raw - median_interest) * weight
            note = (
                "" if weight >= 1 else f", shrunk to {signals['demand']:.0f} for small-state noise"
            )
            reasons.append(f"Google Trends interest {raw:.0f}/100 in {name}{note}.")
        else:
            state_confidence -= 8 if trends else 3
            if trends:
                reasons.append("No Google Trends reading for this state.")

        if has_targets:
            hit = name in targeted_states or normalise(state.language) in targeted_languages
            signals["targeting"] = 100.0 if hit else NOT_TARGETED
            if hit:
                reasons.append(f"Planned localization/targeting covers {name} ({state.language}).")

        if name in survey:
            found = survey[name]
            signals["survey"] = found["survey_affinity"]
            reasons.append(
                f"Survey affinity index {found['survey_index']:.0f} "
                f"(100 = state average, n={found['survey_n']:.0f})."
            )
            state_confidence += 4 if found["survey_n"] >= 200 else 1

        if state.population < SMALL_STATE:
            state_confidence -= 4
        weight_total = sum(WEIGHTS[key] for key in signals)
        composite = sum(signals[key] * WEIGHTS[key] for key in signals) / weight_total
        score = TITLE_ANCHOR * market_score + (1 - TITLE_ANCHOR) * composite
        rows.append(
            RegionalScore(
                state=name,
                score=round(max(0.0, min(100.0, score)), 2),
                confidence=round(max(0.0, min(100.0, state_confidence)), 2),
                recommended_language=state.language,
                preferred_platform=platform,
                reasons=reasons,
            )
        )
    return sorted(rows, key=lambda row: row.score, reverse=True)
