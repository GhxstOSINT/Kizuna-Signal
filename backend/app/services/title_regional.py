"""Rule-based state scores (0-100) from a title's genre and name, nothing else.

state score = 80% genre + 20% title name
  genre       how strongly viewers in that state over-index on the title's genre (survey affinity,
              100 = the state's average viewer, mapped to 0-100 by Affinity.score).
  title name  one score for the whole title, so it shifts every state equally; only genre separates
              states. See ``name_score`` for the rules.
These are transparent heuristics, not the trained regional model, and the default survey rows are
simulated (labelled PROXY). The reasons attached to each state say so.
"""

from __future__ import annotations

import re
from functools import lru_cache

from app.db.models import Title
from app.schemas.analysis import RegionalScore
from app.services import census
from app.services.survey import Affinity, SurveyData

GENRE_WEIGHT = 0.8
NAME_WEIGHT = 0.2
PRIMARY_SHARE = 0.6  # of the genre part when the title also lists secondary genres

# The census table splits these; the dashboard and the rest of the API treat them as one region.
MERGED = {
    "Dadra and Nagar Haveli": "Dadra and Nagar Haveli and Daman and Diu",
    "Daman and Diu": "Dadra and Nagar Haveli and Daman and Diu",
}
DISPLAY = {"Jammu & Kashmir": "Jammu and Kashmir"}


@lru_cache
def load_survey(directory: str) -> SurveyData:
    return SurveyData.from_dir(directory)


def name_score(title: Title) -> tuple[float, list[str]]:
    """0-100 for how easy the title name is to remember, say and search for, with the rules hit."""
    shown = (title.english_title or title.name).strip()
    words = len(shown.split())
    score, notes = 50.0, []
    if words <= 3:
        score += 20
        notes.append(f"short ({words} word{'s' if words != 1 else ''})")
    elif words <= 5:
        score += 10
        notes.append(f"{words} words")
    else:
        score -= 10
        notes.append(f"long ({words} words)")
    if len(shown) <= 24:
        score += 10
        notes.append("compact")
    elif len(shown) > 40:
        score -= 10
        notes.append("over 40 characters")
    if re.search(r"[A-Za-z]", shown):
        score += 10
        notes.append("readable in Latin script")
    else:
        score -= 15
        notes.append("no Latin-script title to search for")
    if title.english_title and title.english_title.strip() != title.name.strip():
        score += 5
        notes.append("has a separate English title")
    return max(0.0, min(100.0, score)), notes


def _genre_part(
    survey: SurveyData, state: str | None, primary: str, secondary: set[str]
) -> tuple[float, Affinity] | None:
    first = survey.affinity(state, {primary})
    rest = survey.affinity(state, secondary) if secondary else None
    if first and rest:
        return PRIMARY_SHARE * first.score + (1 - PRIMARY_SHARE) * rest.score, first
    found = first or rest
    return (found.score, found) if found else None


def calculate_title_regional_scores(title: Title, survey: SurveyData) -> list[RegionalScore]:
    """Every census state/UT scored from genre and title name, best first. Empty if no survey data."""
    if survey.empty:
        return []
    primary = title.primary_genre
    secondary = {genre for genre in title.genres if genre.lower() != primary.lower()}
    name_value, name_notes = name_score(title)
    platform = title.target_platform if title.target_platform.lower() != "undecided" else "OTT"
    simulated = lambda affinity: any("PROXY" in source for source in affinity.sources)  # noqa: E731

    scored: dict[str, RegionalScore] = {}
    for state in census.all_states().values():
        found = _genre_part(survey, state.name, primary, secondary)
        national = False
        if found is None:  # no row for this state: use the national viewer for the genre
            found = _genre_part(survey, None, primary, secondary)
            national = True
        if found is None:
            continue
        genre_value, evidence = found
        value = round(GENRE_WEIGHT * genre_value + NAME_WEIGHT * name_value, 2)
        scope = "India-wide (no state rows)" if national else state.name
        reasons = [
            f"Genre: {primary} viewers in {scope} index {evidence.index:.0f} "
            f"(100 = average viewer), a genre score of {genre_value:.0f}/100"
            + (" from simulated PROXY survey rows." if simulated(evidence) else "."),
            f"Title name: {name_value:.0f}/100 ({', '.join(name_notes)}).",
            f"Score = {GENRE_WEIGHT:.0%} genre + {NAME_WEIGHT:.0%} title name = {value:.0f}.",
        ]
        name = DISPLAY.get(state.name, state.name)
        confidence = round(40 + min(35.0, evidence.sample_size / 200), 2)
        if national:
            confidence = min(confidence, 45.0)
        region = RegionalScore(
            state=name,
            score=value,
            confidence=confidence,
            recommended_language=state.language,
            preferred_platform=platform,
            reasons=reasons,
        )
        merged = MERGED.get(state.name)
        if merged and merged in scored:  # second half of a merged pair: average the two
            other = scored[merged]
            region = other.model_copy(
                update={
                    "score": round((other.score + value) / 2, 2),
                    "confidence": min(other.confidence, confidence),
                }
            )
        scored[merged or name] = region.model_copy(update={"state": merged or name})
    return sorted(scored.values(), key=lambda item: item.score, reverse=True)
