from __future__ import annotations

import json
from pathlib import Path

from app.ml.levenshtein import name_similarity, similarity

MOCK_DIR = Path(__file__).resolve().parents[2] / "data" / "mock"
REAL_COMPARABLES = Path(__file__).resolve().parents[2] / "data" / "real" / "comparables_anilist.json"

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


def tag_genres(*texts: str) -> list[str]:
    blob = " ".join(texts).lower()
    return sorted(g for g, words in KEYWORDS.items() if any(w in blob for w in words))


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_measured_comparables() -> list[dict]:
    """Measured AniList data written by scripts/fetch_real_comparables.py (empty if not fetched)."""
    if not REAL_COMPARABLES.exists():
        return []
    return json.loads(REAL_COMPARABLES.read_text(encoding="utf-8"))["titles"]


def comparable_names() -> list[str]:
    """Display names of every comparable title (mock comparables plus the in-code catalog)."""
    names: list[str] = []
    for path in sorted(MOCK_DIR.glob("*/comparables.json")):
        names.extend(item["title"] for item in _read(path)["comparables"])
    names.extend(["Death Note", "Attack on Titan", "Haikyu!!"])
    unique: list[str] = []
    for name in names:
        if not any(similarity(name, seen) >= DEDUPE_THRESHOLD for seen in unique):
            unique.append(name)
    return unique


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


ANILIST_GENRE_MAP = {"sci-fi": "scifi", "psychological": "mystery", "thriller": "mystery", "horror": "supernatural"}


def _measured_genres(genres: list[str]) -> set[str]:
    mapped = {ANILIST_GENRE_MAP.get(g, g) for g in genres}
    return mapped & set(GENRES)


def load_labeled_corpus() -> list[dict]:
    """Released titles with a 0-100 performance label, de-duplicated by edit distance.

    Labels are the measured AniList signal (see scripts/fetch_real_comparables.py) whenever a
    title was matched there; otherwise the hand-set mock label is kept and tagged as such.
    """
    measured = load_measured_comparables()
    rows: list[dict] = []
    for path in sorted(MOCK_DIR.glob("*/comparables.json")):
        for item in _read(path)["comparables"]:
            hit = next((x for x in measured if name_similarity(x["title"], item["title"]) >= 0.85), None)
            genres = set(tag_genres(item["title"], item["reason"]))
            if hit:
                genres |= _measured_genres(hit["genres"])
            rows.append(
                {
                    "title": item["title"],
                    "description": item["reason"],
                    "genres": sorted(genres),
                    "year": item["year"],
                    "is_film": item["format"].lower().startswith("animated film"),
                    "performance": hit["signal"] if hit else float(item["india_performance"]),
                    "performance_source": "anilist-measured" if hit else "hand-set",
                }
            )
    for hit in measured:  # measured titles that no mock comparable covers
        if any(name_similarity(hit["title"], r["title"]) >= 0.85 for r in rows):
            continue
        rows.append(
            {
                "title": hit["title"],
                "description": " ".join(hit["themes"]),
                "genres": sorted(_measured_genres(hit["genres"])),
                "year": hit["year"] or 2015,
                "is_film": (hit["format"] or "").upper() == "MOVIE",
                "performance": hit["signal"],
                "performance_source": "anilist-measured",
            }
        )

    merged: list[dict] = []
    for row in rows:
        match = next(
            (m for m in merged if similarity(m["title"], row["title"]) >= DEDUPE_THRESHOLD), None
        )
        if match is None:
            merged.append(row)
            continue
        match["genres"] = sorted(set(match["genres"]) | set(row["genres"]))
    return merged
