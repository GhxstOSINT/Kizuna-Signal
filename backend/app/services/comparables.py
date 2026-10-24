from __future__ import annotations

import re

from app.db.models import Title
from app.schemas.analysis import ComparableTitle
from app.services.sources.base import SourceEvidence

CATALOG = [
    {
        "title": "Jujutsu Kaisen",
        "genres": {"action", "fantasy", "supernatural"},
        "themes": {"friendship", "school", "spirits"},
        "signal": 88,
    },
    {
        "title": "Demon Slayer",
        "genres": {"action", "fantasy", "adventure"},
        "themes": {"family", "demons", "journey"},
        "signal": 91,
    },
    {
        "title": "Death Note",
        "genres": {"thriller", "supernatural", "mystery"},
        "themes": {"morality", "crime", "strategy"},
        "signal": 86,
    },
    {
        "title": "Spy x Family",
        "genres": {"comedy", "action", "family"},
        "themes": {"found family", "espionage", "school"},
        "signal": 82,
    },
    {
        "title": "Your Name",
        "genres": {"romance", "fantasy", "drama"},
        "themes": {"identity", "memory", "youth"},
        "signal": 84,
    },
    {
        "title": "Attack on Titan",
        "genres": {"action", "drama", "fantasy"},
        "themes": {"survival", "war", "freedom"},
        "signal": 90,
    },
    {
        "title": "Haikyu",
        "genres": {"sports", "comedy", "drama"},
        "themes": {"underdog", "teamwork", "school"},
        "signal": 79,
    },
    {
        "title": "Naruto",
        "genres": {"action", "adventure", "fantasy"},
        "themes": {"underdog", "friendship", "rivalry"},
        "signal": 89,
    },
]


def normalize_terms(values: list[str]) -> set[str]:
    result: set[str] = set()
    for value in values:
        result.update(re.findall(r"[a-z0-9]+", value.lower()))
    return result


def find_comparables(
    title: Title,
    limit: int = 5,
    evidence: list[SourceEvidence] | None = None,
    allow_catalog: bool = True,
) -> list[ComparableTitle]:
    """Reference titles: discovered by AniList evidence when present, else the demo catalogue.

    The catalogue's signals are invented demo numbers, so live analyses pass allow_catalog=False
    and get no comparables (an unmeasured component) rather than fabricated ones.
    """
    discovered = [
        ComparableTitle(**item)
        for entry in evidence or []
        if entry.status != "unavailable"
        for item in entry.comparables
    ]
    if discovered:
        return sorted(
            discovered, key=lambda item: (item.similarity, item.market_signal), reverse=True
        )[:limit]
    if not allow_catalog:
        return []
    title_genres = normalize_terms([title.primary_genre, *title.genres])
    title_themes = normalize_terms(title.themes)
    synopsis_terms = normalize_terms([title.synopsis])
    results: list[ComparableTitle] = []

    for item in CATALOG:
        genre_overlap = len(title_genres & item["genres"]) / max(
            1, len(title_genres | item["genres"])
        )
        theme_overlap = len(title_themes & item["themes"]) / max(
            1, len(title_themes | item["themes"])
        )
        synopsis_overlap = len(synopsis_terms & item["themes"]) / max(1, len(item["themes"]))
        similarity = min(
            0.96, 0.45 + 0.32 * genre_overlap + 0.15 * theme_overlap + 0.08 * synopsis_overlap
        )
        reasons = []
        common_genres = sorted(title_genres & item["genres"])
        common_themes = sorted(title_themes & item["themes"])
        if common_genres:
            reasons.append(f"Genre overlap: {', '.join(common_genres)}")
        if common_themes:
            reasons.append(f"Theme overlap: {', '.join(common_themes)}")
        if not reasons:
            reasons.append("General audience and format proximity")
        results.append(
            ComparableTitle(
                title=item["title"],
                similarity=round(similarity, 3),
                market_signal=float(item["signal"]),
                reasons=reasons,
            )
        )

    return sorted(results, key=lambda item: (item.similarity, item.market_signal), reverse=True)[
        :limit
    ]
