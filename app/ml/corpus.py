from __future__ import annotations

import json
from pathlib import Path

from app.ml.levenshtein import similarity

MOCK_DIR = Path(__file__).resolve().parents[2] / "data" / "mock"

GENRES = (
    "action",
    "adventure",
    "comedy",
    "drama",
    "fantasy",
    "mystery",
    "romance",
    "scifi",
    "sports",
    "supernatural",
)

KEYWORDS = {
    "action": ("action", "battle", "fight", "power-growth"),
    "adventure": ("adventure", "journey", "quest"),
    "comedy": ("comedy", "comic", "humor", "parody", "gag"),
    "drama": ("drama", "grief", "relationship", "emotional", "reflective"),
    "fantasy": ("fantasy", "folklore", "magic", "isekai"),
    "mystery": ("mystery", "psychological", "thriller", "crime", "suspense"),
    "romance": ("romance", "romantic", "love"),
    "scifi": ("sci-fi", "science", "robot", "futur", "cyber"),
    "sports": ("sport", "team", "racing", "league"),
    "supernatural": ("supernatural", "spirit", "demon", "curse", "ghost", "yokai"),
}
DEDUPE_THRESHOLD = 0.82
# Release years for catalog-only titles (the catalog itself carries no year).
KNOWN_YEARS = {"Death Note": 2006, "Attack on Titan": 2013, "Haikyu": 2014}


def tag_genres(*texts: str) -> list[str]:
    blob = " ".join(texts).lower()
    return sorted(g for g, words in KEYWORDS.items() if any(w in blob for w in words))


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_existing_titles() -> list[dict]:
    """The pre-release titles already in the system (title, description, genre, platform, budget)."""
    records = []
    for path in sorted(MOCK_DIR.glob("*/title.json")):
        data = _read(path)
        records.append(
            {
                "id": data["title_id"],
                "title": data["title"],
                "description": data["synopsis"],
                "genres": data["genres"],
                "platform": data["target_platform"],
                "budget": data["budget_band"],
                "format": data["format"],
            }
        )
    return records


def load_labeled_corpus() -> list[dict]:
    """Released titles with an India performance label (0-100), de-duplicated by edit distance.

    Sources: mock comparables (india_performance) and the in-code comparable catalog
    (market_signal). Titles found in both are merged by Levenshtein name matching.
    """
    from app.services.comparables import CATALOG

    rows: list[dict] = []
    for path in sorted(MOCK_DIR.glob("*/comparables.json")):
        for item in _read(path)["comparables"]:
            rows.append(
                {
                    "title": item["title"],
                    "description": item["reason"],
                    "genres": tag_genres(item["title"], item["reason"]),
                    "year": item["year"],
                    "is_film": item["format"].lower().startswith("animated film"),
                    "performance": float(item["india_performance"]),
                }
            )
    for item in CATALOG:
        rows.append(
            {
                "title": item["title"],
                "description": " ".join(sorted(item["themes"])),
                "genres": sorted(g for g in item["genres"] if g in GENRES),
                "year": None,
                "is_film": item["title"] == "Your Name",
                "performance": float(item["signal"]),
            }
        )

    merged: list[dict] = []
    for row in rows:
        match = next(
            (m for m in merged if similarity(m["title"], row["title"]) >= DEDUPE_THRESHOLD), None
        )
        if match is None:
            merged.append({**row, "_perf": [row["performance"]]})
            continue
        match["_perf"].append(row["performance"])
        match["genres"] = sorted(set(match["genres"]) | set(row["genres"]))
        match["year"] = match["year"] or row["year"]
        if len(row["description"]) > len(match["description"]):
            match["description"] = row["description"]
    for m in merged:
        m["performance"] = round(sum(m["_perf"]) / len(m["_perf"]), 2)
        m["year"] = m["year"] or KNOWN_YEARS[m["title"]]
        del m["_perf"]
    return merged
