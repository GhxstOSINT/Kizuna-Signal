"""Levenshtein edit-distance scoring for titles, descriptions, genres, platforms and budgets."""

from __future__ import annotations

from app.services.textmatch import normalise

GENRE_VOCABULARY = (
    "action",
    "adventure",
    "comedy",
    "drama",
    "fantasy",
    "horror",
    "mystery",
    "psychological",
    "romance",
    "sci-fi",
    "slice of life",
    "sports",
    "supernatural",
    "thriller",
    "coming of age",
)
PLATFORM_VOCABULARY = ("ott", "theatrical", "broadcast tv", "undecided")
BUDGET_VOCABULARY = ("low", "medium", "high")

FIELD_WEIGHTS = {
    "title": 0.20,
    "description": 0.30,
    "genre": 0.25,
    "platform": 0.10,
    "budget": 0.15,
}


def levenshtein_distance(a: str, b: str) -> int:
    """Classic edit distance (insert, delete, substitute), O(len(a)*len(b)) time, O(min) memory."""
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def similarity(a: str, b: str) -> float:
    """Normalized Levenshtein similarity in [0, 1]; 1 means identical after normalization."""
    a, b = normalise(a), normalise(b)
    if not a and not b:
        return 1.0
    longest = max(len(a), len(b))
    return 1.0 - levenshtein_distance(a, b) / longest


def name_similarity(a: str, b: str) -> float:
    """Title matching: Levenshtein similarity, with a word-boundary prefix rule so
    "Demon Slayer" matches "Demon Slayer: Kimetsu no Yaiba" (scored 0.85, never 1.0)."""
    base = similarity(a, b)
    na, nb = normalise(a), normalise(b)
    short, long_ = sorted((na, nb), key=len)
    if short and len(short) >= 5 and long_.startswith(short + " "):
        return max(base, 0.85)
    return base


def token_sort_similarity(a: str, b: str) -> float:
    """Order-insensitive variant, used for genre lists and long descriptions."""
    key = lambda s: " ".join(sorted(normalise(s).split()))  # noqa: E731
    return similarity(key(a), key(b))


def best_vocabulary_match(value: str, vocabulary: tuple[str, ...]) -> tuple[str, float]:
    match = max(vocabulary, key=lambda term: similarity(value, term))
    return match, round(similarity(value, match), 4)


def vocabulary_confidence(values: list[str], vocabulary: tuple[str, ...]) -> float:
    """Mean best-match similarity of declared values against a canonical vocabulary."""
    if not values:
        return 0.0
    return round(sum(best_vocabulary_match(v, vocabulary)[1] for v in values) / len(values), 4)


def compare_records(left: dict, right: dict) -> dict:
    """Per-field Levenshtein scores (0-100) and a weighted composite.

    A field missing on either side is reported as None and excluded; the remaining
    weights are renormalised so absent data never inflates or deflates the composite.
    """
    fields: dict[str, float | None] = {}
    fields["title"] = _score(left.get("title"), right.get("title"), similarity)
    fields["description"] = _score(
        left.get("description"), right.get("description"), token_sort_similarity
    )
    fields["genre"] = _score(
        " ".join(sorted(left.get("genres") or [])),
        " ".join(sorted(right.get("genres") or [])),
        token_sort_similarity,
    )
    fields["platform"] = _score(left.get("platform"), right.get("platform"), similarity)
    fields["budget"] = _score(left.get("budget"), right.get("budget"), similarity)
    used = {k: v for k, v in fields.items() if v is not None}
    total = sum(FIELD_WEIGHTS[k] for k in used)
    composite = sum(FIELD_WEIGHTS[k] * v for k, v in used.items()) / total if total else 0.0
    return {"fields": fields, "composite": round(composite, 2), "fields_used": sorted(used)}


def _score(a, b, fn) -> float | None:
    if not a or not b:
        return None
    return round(100 * fn(str(a), str(b)), 2)
