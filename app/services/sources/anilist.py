from __future__ import annotations

import logging
import math
import re
import time
from collections.abc import Callable

import httpx

from app.db.models import Title
from app.services.sources.base import MALFORMED_RESPONSE_ERRORS, SourceAdapter, SourceEvidence
from app.services.textmatch import match_score, normalise

logger = logging.getLogger(__name__)

API_URL = "https://graphql.anilist.co"
MIN_MATCH = 0.85
POOL_SIZE = 50
COMPARABLE_LIMIT = 5
# Comparables come from a genre's most popular titles, so raw popularity overstates what a
# typical title achieves; their signal is discounted by this factor.
TOP_POOL_DISCOUNT = 0.85
# Popularity (users who list a title) of 1k maps to 0 and 1M to 100 on a log scale.
POPULARITY_FLOOR = 3.0
POPULARITY_CEILING = 6.0

LOOKUP_QUERY = """
query ($search: String) {
  Page(perPage: 8) {
    media(search: $search, type: ANIME, isAdult: false, sort: SEARCH_MATCH) {
      id title { romaji english native } popularity favourites averageScore
      genres tags { name rank } format status seasonYear description(asHtml: false)
    }
  }
}"""
POOL_QUERY = """
query ($genres: [String]) {
  Page(perPage: __N__) {
    media(type: ANIME, isAdult: false, genre_in: $genres, sort: POPULARITY_DESC,
          format_in: [TV, MOVIE, ONA]) {
      id title { romaji english } popularity averageScore genres tags { name rank }
    }
  }
}""".replace("__N__", str(POOL_SIZE))

# AniList's fixed genre vocabulary; adult genres are deliberately excluded.
GENRES = {
    "action": "Action", "adventure": "Adventure", "comedy": "Comedy", "drama": "Drama",
    "fantasy": "Fantasy", "horror": "Horror", "mahou shoujo": "Mahou Shoujo",
    "magical girl": "Mahou Shoujo", "mecha": "Mecha", "music": "Music", "mystery": "Mystery",
    "psychological": "Psychological", "romance": "Romance", "sci fi": "Sci-Fi",
    "scifi": "Sci-Fi", "science fiction": "Sci-Fi", "slice of life": "Slice of Life",
    "sports": "Sports", "sport": "Sports", "supernatural": "Supernatural", "thriller": "Thriller",
}  # fmt: skip
SEQUEL = re.compile(r"\b(season|part|cour)\b|\b\d+(st|nd|rd|th)\b|\bII+\b", re.IGNORECASE)


class AniListError(Exception):
    pass


class AniListRateLimited(AniListError):
    def __init__(self, retry_after: float):
        super().__init__("rate limited")
        self.retry_after = retry_after


def popularity_signal(popularity: int) -> float:
    if popularity <= 0:
        return 0.0
    span = POPULARITY_CEILING - POPULARITY_FLOOR
    return max(0.0, min(100.0, 100 * (math.log10(popularity) - POPULARITY_FLOOR) / span))


def anilist_genres(title: Title) -> list[str]:
    seen: list[str] = []
    for raw in [title.primary_genre, *title.genres]:
        mapped = GENRES.get(normalise(raw))
        if mapped and mapped not in seen:
            seen.append(mapped)
    return seen


class AniListAdapter(SourceAdapter):
    """Title metadata, fan-community strength and genre comparables from AniList (no key)."""

    name = "anilist"
    _cache: dict[str, tuple[float, SourceEvidence]] = {}
    _blocked_until: float = 0.0

    def __init__(
        self,
        client: httpx.Client,
        cache_ttl_seconds: int = 24 * 3600,
        cooldown_seconds: int = 60,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.client = client
        self.cache_ttl_seconds = cache_ttl_seconds
        self.cooldown_seconds = cooldown_seconds
        self.clock = clock

    def collect(self, title: Title) -> SourceEvidence:
        queries = [q for q in (title.english_title, title.name) if q]
        genres = anilist_genres(title)
        key = "|".join([normalise(queries[0]) if queries else "", *genres])
        now = self.clock()
        cached = self._cache.get(key)
        if cached and now - cached[0] < self.cache_ttl_seconds:
            return self._as_cached(cached[1])
        if now < AniListAdapter._blocked_until:
            wait = int(AniListAdapter._blocked_until - now)
            return self._unavailable(
                title, f"AniList is rate limiting this server; retry in ~{wait}s."
            )
        try:
            evidence = self._collect(title, queries, genres)
        except AniListRateLimited as exc:
            AniListAdapter._blocked_until = now + max(exc.retry_after, self.cooldown_seconds)
            return self._unavailable(title, "AniList rate limit reached; metadata not collected.")
        except (httpx.HTTPError, AniListError, ValueError) as exc:
            logger.warning("anilist_unavailable", extra={"title": title.name, "error": str(exc)})
            return self._unavailable(title, f"AniList request failed: {exc}")
        except MALFORMED_RESPONSE_ERRORS as exc:
            logger.warning("anilist_malformed", extra={"title": title.name, "error": repr(exc)})
            return self._unavailable(title, "AniList returned a response in an unexpected format.")
        if evidence.status == "available":
            self._cache[key] = (now, evidence)
        return evidence

    def _collect(self, title: Title, queries: list[str], genres: list[str]) -> SourceEvidence:
        matched = self._find_title(queries)
        pool = self._pool(genres[:2]) if len(genres) >= 2 else []
        if len(pool) < COMPARABLE_LIMIT and genres:
            pool = self._pool(genres[:1])
        comparables = self._rank_comparables(title, genres, pool, matched)
        if matched is None and not comparables:
            return self._unavailable(
                title, "AniList has no matching title and no comparable genre pool."
            )

        metrics: dict[str, float] = {"comparable_pool": float(len(comparables))}
        warnings = [
            "AniList popularity is a global fan-community signal, not Indian viewership; "
            "comparables are drawn from the most popular titles in the genre."
        ]
        provenance = {"mode": "live", "api": "anilist-graphql", "genres": ",".join(genres)}
        if matched:
            pop = popularity_signal(matched["popularity"])
            score = matched.get("averageScore")
            metrics["community_strength"] = round(0.6 * pop + 0.4 * score if score else pop, 2)
            fields = ["genres", "tags", "averageScore", "description", "seasonYear", "format"]
            metrics["metadata_completeness"] = round(
                100 * sum(bool(matched.get(f)) for f in fields) / len(fields), 2
            )
            provenance["anilist_id"] = str(matched["id"])
        else:
            warnings.append("Title is not listed on AniList yet; only genre comparables are used.")
        if comparables:
            top = comparables[:COMPARABLE_LIMIT]
            metrics["historical_affinity"] = round(
                sum(c["market_signal"] for c in top) / len(top), 2
            )

        return SourceEvidence(
            source=self.name,
            status="available",
            freshness_score=1.0,
            quality_score=0.9 if matched else 0.6,
            metrics=metrics,
            warnings=warnings,
            provenance=provenance,
            comparables=comparables,
        )

    def _post(self, query: str, variables: dict) -> dict:
        response = self.client.post(API_URL, json={"query": query, "variables": variables})
        if response.status_code == 429:
            raise AniListRateLimited(float(response.headers.get("Retry-After", 60)))
        if response.status_code != 200:
            raise AniListError(f"HTTP {response.status_code}")
        payload = response.json()
        if payload.get("errors"):
            raise AniListError(payload["errors"][0].get("message", "GraphQL error"))
        return payload["data"]["Page"]["media"]

    def _find_title(self, queries: list[str]) -> dict | None:
        best: tuple[float, int, dict] | None = None
        for query in queries:
            for media in self._post(LOOKUP_QUERY, {"search": query}):
                names = [n for n in media["title"].values() if n]
                score = max((match_score(query, n) for n in names), default=0.0)
                if score >= MIN_MATCH and (best is None or (score, media["popularity"]) > best[:2]):
                    best = (score, media["popularity"], media)
        return best[2] if best else None

    def _pool(self, genres: list[str]) -> list[dict]:
        return self._post(POOL_QUERY, {"genres": genres}) if genres else []

    def _rank_comparables(
        self, title: Title, genres: list[str], pool: list[dict], matched: dict | None
    ) -> list[dict]:
        wanted_genres = {g.casefold() for g in genres}
        wanted_themes = {normalise(t) for t in [*title.themes]}
        if matched:  # a listed title's own tags describe it better than user-entered themes
            wanted_genres |= {g.casefold() for g in matched.get("genres", [])}
            wanted_themes |= {normalise(t["name"]) for t in matched["tags"] if t["rank"] >= 50}
        own = {normalise(q) for q in (title.name, title.english_title) if q}
        ranked: list[dict] = []
        for media in pool:
            names = [n for n in media["title"].values() if n]
            if matched and media["id"] == matched["id"]:
                continue
            if any(match_score(o, n) >= MIN_MATCH for o in own for n in names):
                continue
            display = media["title"].get("english") or media["title"]["romaji"]
            if SEQUEL.search(display):
                continue
            their_genres = {g.casefold() for g in media["genres"]}
            their_tags = {normalise(t["name"]) for t in media["tags"] if t["rank"] >= 40}
            genre_sim = len(wanted_genres & their_genres) / max(
                1, len(wanted_genres | their_genres)
            )
            theme_hits = wanted_themes & their_tags
            theme_sim = len(theme_hits) / max(1, len(wanted_themes))
            similarity = min(0.95, 0.35 + 0.45 * genre_sim + 0.25 * theme_sim)
            reasons = []
            if wanted_genres & their_genres:
                reasons.append("Genre overlap: " + ", ".join(sorted(wanted_genres & their_genres)))
            if theme_hits:
                reasons.append("Theme overlap: " + ", ".join(sorted(theme_hits)))
            reasons.append(
                f"AniList popularity {media['popularity']:,} (global, top-of-genre discounted)"
            )
            ranked.append(
                {
                    "title": display,
                    "similarity": round(similarity, 3),
                    "market_signal": round(
                        TOP_POOL_DISCOUNT * popularity_signal(media["popularity"]), 2
                    ),
                    "reasons": reasons,
                    "key": normalise(display),
                }
            )
        ranked.sort(key=lambda c: (c["similarity"], c["market_signal"]), reverse=True)
        chosen: list[dict] = []
        for candidate in ranked:  # drop franchise duplicates such as "X" and "X: The Movie"
            if not any(
                candidate["key"].startswith(c["key"]) or c["key"].startswith(candidate["key"])
                for c in chosen
            ):
                chosen.append(candidate)
        return [{k: v for k, v in c.items() if k != "key"} for c in chosen[:COMPARABLE_LIMIT]]

    @staticmethod
    def _as_cached(evidence: SourceEvidence) -> SourceEvidence:
        return SourceEvidence(
            source=evidence.source,
            status="cached",
            freshness_score=0.9,
            quality_score=evidence.quality_score,
            metrics=dict(evidence.metrics),
            warnings=list(evidence.warnings),
            provenance={**evidence.provenance, "cache": "hit"},
            comparables=[dict(c) for c in evidence.comparables],
        )

    def _unavailable(self, title: Title, warning: str) -> SourceEvidence:
        return SourceEvidence(
            source=self.name,
            status="unavailable",
            freshness_score=0.0,
            quality_score=0.0,
            warnings=[warning],
            provenance={"mode": "live", "title": title.name},
        )
