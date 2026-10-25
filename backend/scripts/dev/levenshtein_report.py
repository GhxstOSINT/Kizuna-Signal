"""Levenshtein similarity report for the titles stored in the database.

    python backend/scripts/dev/levenshtein_report.py [output.json]

For every stored title: genre, platform and budget confidence against the known vocabularies, and
its closest other stored title scored on title, description, genre, platform and budget (0-100).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import select

from app.db.models import Title
from app.db.session import SessionLocal
from app.services.levenshtein import (
    BUDGET_VOCABULARY,
    GENRE_VOCABULARY,
    PLATFORM_VOCABULARY,
    compare_records,
    vocabulary_confidence,
)


def record(title: Title) -> dict:
    return {
        "id": title.id,
        "title": title.english_title or title.name,
        "description": title.synopsis,
        "genres": [title.primary_genre, *title.genres],
        "platform": title.target_platform,
        "budget": title.marketing_budget,
    }


def build_report(titles: list[Title]) -> list[dict]:
    records = [record(title) for title in titles]
    report = []
    for item in records:
        peers = [other for other in records if other["id"] != item["id"]]
        nearest = max(
            ({"against": p["title"], **compare_records(item, p)} for p in peers),
            key=lambda match: match["composite"],
            default=None,
        )
        report.append(
            {
                "title": item["title"],
                "genre_confidence": round(
                    100 * vocabulary_confidence(item["genres"], GENRE_VOCABULARY), 1
                ),
                "platform_confidence": round(
                    100 * vocabulary_confidence([item["platform"]], PLATFORM_VOCABULARY), 1
                ),
                "budget_confidence": round(
                    100 * vocabulary_confidence([item["budget"]], BUDGET_VOCABULARY), 1
                ),
                "nearest_title": nearest,
            }
        )
    return report


def main() -> None:
    with SessionLocal() as db:
        report = build_report(list(db.scalars(select(Title))))
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
        print(f"Wrote {sys.argv[1]}")
    else:
        print(text)


if __name__ == "__main__":
    main()
