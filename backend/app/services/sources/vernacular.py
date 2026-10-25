"""Native-script title names and multi-term state interest for Google Trends.

People search for a title in their own language and script, so the state split of an English
search term understates interest in states where that language dominates. Native names come from
Wikipedia language links; per-state interest from several terms is averaged, with a term in a
state's own language counting double there.
"""

from __future__ import annotations

import logging

import httpx

from app.db.models import Title
from app.services import census
from app.services.textmatch import match_score

logger = logging.getLogger(__name__)

WIKI_API = "https://en.wikipedia.org/w/api.php"
MIN_ARTICLE_MATCH = 0.8
LOCAL_LANGUAGE_WEIGHT = 2.0

# Wikipedia language code per census state language.
LANGUAGE_CODES = {
    "hindi": "hi",
    "bengali": "bn",
    "tamil": "ta",
    "marathi": "mr",
    "telugu": "te",
    "kannada": "kn",
    "malayalam": "ml",
    "gujarati": "gu",
    "punjabi": "pa",
    "odia": "or",
    "assamese": "as",
    "urdu": "ur",
}


def state_language_code(state: str) -> str | None:
    profile = census.resolve_state(state)
    return LANGUAGE_CODES.get(profile.language.casefold()) if profile else None


def term_languages_by_population() -> list[str]:
    """Wikipedia language codes ordered by the population of the states that speak them."""
    weight: dict[str, int] = {}
    for profile in census.all_states().values():
        code = LANGUAGE_CODES.get(profile.language.casefold())
        if code:
            weight[code] = weight.get(code, 0) + profile.population
    return sorted(weight, key=lambda code: -weight[code])


def vernacular_terms(client: httpx.Client, title: Title) -> list[tuple[str, str]]:
    """(language code, native-script name) pairs for the title, most populous language first.

    Empty when the title has no matching Wikipedia article or the article has no translations.
    Failures are logged and swallowed: native names only enrich the English search term.
    """
    names = [n for n in dict.fromkeys([title.english_title or "", title.name]) if n]
    try:
        article = None
        for name in names:
            response = client.get(
                WIKI_API,
                params={"action": "opensearch", "search": name, "limit": 5, "format": "json"},
            )
            response.raise_for_status()
            options = response.json()[1]
            scored = [(max(match_score(n, o) for n in names), o) for o in options]
            best = max(scored, default=(0.0, ""))
            if best[0] >= MIN_ARTICLE_MATCH:
                article = best[1]
                break
        if article is None:
            return []
        response = client.get(
            WIKI_API,
            params={
                "action": "query",
                "titles": article,
                "prop": "langlinks",
                "lllimit": 500,
                "format": "json",
            },
        )
        response.raise_for_status()
        pages = response.json().get("query", {}).get("pages", {})
        links = next(iter(pages.values()), {}).get("langlinks", [])
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
        logger.warning("vernacular_terms_failed", extra={"title": title.name, "error": str(exc)})
        return []
    found = {
        link["lang"]: link["*"] for link in links if link.get("lang") in LANGUAGE_CODES.values()
    }
    return [(code, found[code]) for code in term_languages_by_population() if code in found]


def combine_state_interest(
    vectors: list[tuple[str, dict[str, float]]],
) -> dict[str, float]:
    """Average several terms' per-state interest (each 0-100, top state = 100).

    `vectors` holds (language code, {state: interest}). A term in a state's own language counts
    double in that state. All-zero vectors are skipped; states are returned only if some term
    measured them.
    """
    usable = [(lang, vec) for lang, vec in vectors if vec and max(vec.values()) > 0]
    states = {state for _, vec in usable for state in vec}
    out: dict[str, float] = {}
    for state in states:
        total = weight_sum = 0.0
        for lang, vec in usable:
            if state in vec:
                weight = LOCAL_LANGUAGE_WEIGHT if lang == state_language_code(state) else 1.0
                total += weight * vec[state]
                weight_sum += weight
        out[state] = round(total / weight_sum, 2)
    return out
