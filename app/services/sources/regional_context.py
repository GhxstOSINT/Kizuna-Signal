from __future__ import annotations

import math

from app.db.models import Title
from app.services import census
from app.services.sources.base import SourceAdapter, SourceEvidence
from app.services.survey import SurveyData

LANGUAGE_REACH_TARGET = 0.5  # target languages spoken by half of India count as full reach
PROXY_MARK = "PROXY"  # survey `source` text marking exploratory, non-representative rows
MARKET_TARGET = 0.8  # target states/languages covering 80% of urban India count as full


def title_genres(title: Title) -> set[str]:
    return {title.primary_genre, *title.genres}


class RegionalContextAdapter(SourceAdapter):
    """India regional context from Census 2011 tables plus optional survey CSVs. No network."""

    name = "regional_context"

    def __init__(self, survey: SurveyData | None = None):
        self.survey = survey or SurveyData()

    def collect(self, title: Title) -> SourceEvidence:
        metrics: dict[str, float] = {}
        warnings = [
            f"Census context is from {census.CENSUS_YEAR} tables; it describes population "
            "and language, not current viewing behaviour."
        ]
        language_states = census.states_for_languages(title.target_languages)
        explicit = [s for s in map(census.resolve_state, title.target_states) if s is not None]

        if title.target_languages and language_states:
            reach = census.population_share(language_states)
            metrics["language_fit"] = round(
                100 * math.sqrt(min(1.0, reach / LANGUAGE_REACH_TARGET)), 2
            )
        if language_states or explicit:
            share = census.population_share([*language_states, *explicit], urban_weighted=True)
            metrics["addressable_market"] = round(
                100 * math.sqrt(min(1.0, share / MARKET_TARGET)), 2
            )
        else:
            warnings.append(
                "No target languages or states were supplied; addressable market not measured."
            )

        regional: dict[str, dict[str, float]] = {}
        provenance = {
            "mode": "static-census",
            "table": f"census-{census.CENSUS_YEAR}",
            "survey_rows": str(len(self.survey.rows)),
        }
        quality = 0.7
        if self.survey.empty:
            warnings.append(
                "No survey data loaded; state preferences rely on search interest only."
            )
        else:
            genres = title_genres(title)
            national = self.survey.affinity(None, genres, title.content_format)
            if national:
                metrics["genre_affinity"] = national.score
                provenance["survey_sources"] = ", ".join(national.sources)
            for state in census.all_states():
                found = self.survey.affinity(state, genres, title.content_format)
                if found:
                    regional[state] = {
                        "survey_affinity": found.score,
                        "survey_index": round(found.index, 1),
                        "survey_n": found.sample_size,
                    }
            if national or regional:
                used = set(national.sources if national else ())
                for state in regional:
                    found = self.survey.affinity(state, genres, title.content_format)
                    used |= set(found.sources if found else ())
                if all(PROXY_MARK in source for source in used):
                    quality = 0.75
                    warnings.append(
                        "Survey signal comes only from rows labelled as exploratory proxies "
                        "(preference or rating data), not measured viewing rates."
                    )
                else:
                    quality = 0.9
            else:
                warnings.append("Survey data has no rows for this title's genres or content type.")
            if stale := self.survey.stale_warning():
                warnings.append(stale)
        for error in self.survey.errors[:5]:
            warnings.append(f"Survey file issue: {error}")

        return SourceEvidence(
            source=self.name,
            status="available",
            freshness_score=0.7,
            quality_score=quality,
            metrics=metrics,
            warnings=warnings,
            provenance=provenance,
            regional=regional,
        )
