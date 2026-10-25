from __future__ import annotations

import json
import re
from pathlib import Path

from app.db.models import Title
from app.schemas.analysis import ComparableTitle

REAL_COMPARABLES = Path(__file__).resolve().parents[2] / "data" / "real" / "comparables_anilist.json"

def _load_catalog() -> list[dict]:
    """Comparable titles with measured AniList genres, themes and popularity/quality signal."""
    if not REAL_COMPARABLES.exists():
        return []
    rows = json.loads(REAL_COMPARABLES.read_text(encoding="utf-8"))["titles"]
    return [
        {
            "title": row["title"],
            "genres": normalize_terms(row["genres"]),
            "themes": normalize_terms(row["themes"]),
            "signal": row["signal"],
        }
        for row in rows
    ]


def normalize_terms(values: list[str]) -> set[str]:
    result: set[str] = set()
    for value in values:
        result.update(re.findall(r"[a-z0-9]+", value.lower()))
    return result


CATALOG: list[dict] = []


def find_comparables(title: Title, limit: int = 5) -> list[ComparableTitle]:
    global CATALOG
    if not CATALOG:
        CATALOG = _load_catalog()
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
