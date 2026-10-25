"""Live public-signal adapters.

Every adapter returns `unavailable` (never fabricated numbers) when a source cannot be reached,
the title cannot be matched, or credentials are missing. Titles are matched to source records
by normalised Levenshtein similarity so a wrong article is rejected instead of scored.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
import time
from dataclasses import asdict, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

from app.core.config import Settings
from app.db.models import Title
from app.ml.census import CENSUS, STATES
from app.ml.levenshtein import name_similarity, normalize
from app.services.sources.base import SourceAdapter, SourceEvidence

MATCH_THRESHOLD = 0.75
CACHE_TTL_SECONDS = 3600
_cache: dict[tuple[str, str], tuple[float, SourceEvidence]] = {}
_trends_blocked_until = 0.0  # unofficial Trends endpoint rate-limits; back off instead of waiting each time

STATE_LANGUAGE = {
    "Maharashtra": "hindi", "Karnataka": "kannada", "Delhi NCR": "hindi", "Tamil Nadu": "tamil",
    "Telangana": "telugu", "West Bengal": "bengali", "Kerala": "malayalam", "Uttar Pradesh": "hindi",
}


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return round(max(low, min(high, value)), 2)


def log_scale(value: float, ceiling: float) -> float:
    """0-100 on a log scale where `ceiling` maps to 100."""
    return clamp(100 * math.log10(1 + max(0.0, value)) / math.log10(1 + ceiling))


def _unavailable(source: str, reason: str, **provenance: str) -> SourceEvidence:
    return SourceEvidence(
        source=source,
        status="unavailable",
        freshness_score=0.0,
        quality_score=0.0,
        warnings=[f"{source}: {reason}"],
        provenance={"mode": "live", **provenance},
    )


def _candidates(title: Title) -> list[str]:
    return [name for name in dict.fromkeys([title.english_title or "", title.name]) if name]


def best_match(title: Title, options: list[str]) -> tuple[str, float] | None:
    """Best option by Levenshtein similarity to any of the title's names, if above threshold."""
    best: tuple[str, float] | None = None
    for option in options:
        cleaned = re.sub(r"\s*\(.*?\)\s*", " ", option).strip()
        score = max(name_similarity(name, cleaned) for name in _candidates(title))
        if best is None or score > best[1]:
            best = (option, score)
    return best if best and best[1] >= MATCH_THRESHOLD else None


def _title_in_video(name: str, video_title: str) -> bool:
    """Every meaningful word of the title appears in the video title (so "Spy x Family"
    matches "SPY×FAMILY Season 2 Official Trailer")."""
    required = [t for t in normalize(name).split() if len(t) > 1]
    words = set(normalize(video_title).split())
    return bool(required) and all(t in words for t in required)


class _HttpAdapter(SourceAdapter):
    def __init__(self, client: httpx.Client, settings: Settings):
        self.client = client
        self.settings = settings

    @property
    def headers(self) -> dict[str, str]:
        return {"User-Agent": f"KizunaSignal/0.2 (+{self.settings.source_contact_url})"}

    def collect(self, title: Title) -> SourceEvidence:
        key = (self.name, title.name.lower())
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < CACHE_TTL_SECONDS:
            cached = hit[1]
            return replace(cached, status="cached")
        try:
            evidence = self._collect(title)
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            evidence = _unavailable(self.name, f"request failed ({type(exc).__name__})")
        if evidence.status == "available":
            _cache[key] = (time.time(), evidence)
        return evidence

    def _collect(self, title: Title) -> SourceEvidence:
        raise NotImplementedError


def resolve_article(client: httpx.Client, headers: dict[str, str], title: Title) -> tuple[str, float] | None:
    """The English Wikipedia article for a title (Levenshtein-matched), or None."""
    for query in _candidates(title):
        r = client.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "opensearch", "search": query, "limit": 6, "format": "json"},
            headers=headers,
        )
        r.raise_for_status()
        found = best_match(title, r.json()[1])
        if found:
            return found
    return None


# Wikipedia editions for the state languages, in descending order of covered population.
VERNACULAR_LANGS = ("hi", "bn", "ta", "mr", "te", "kn", "ml")
LOCAL_LANG = {
    "Uttar Pradesh": "hi", "Delhi NCR": "hi", "West Bengal": "bn", "Tamil Nadu": "ta",
    "Maharashtra": "mr", "Telangana": "te", "Karnataka": "kn", "Kerala": "ml",
}


def vernacular_terms(client: httpx.Client, headers: dict[str, str], article: str) -> dict[str, str]:
    """Native-script names of the work from Wikipedia language links (language code -> title)."""
    r = client.get(
        "https://en.wikipedia.org/w/api.php",
        params={"action": "query", "titles": article, "prop": "langlinks", "lllimit": 500,
                "format": "json"},
        headers=headers,
    )
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    links = next(iter(pages.values()), {}).get("langlinks", [])
    found = {link["lang"]: link["*"] for link in links if link["lang"] in VERNACULAR_LANGS}
    return {lang: found[lang] for lang in VERNACULAR_LANGS if lang in found}


class WikimediaLive(_HttpAdapter):
    name = "wikimedia"

    def _collect(self, title: Title) -> SourceEvidence:
        found = resolve_article(self.client, self.headers, title)
        if not found:
            return _unavailable(self.name, "no Wikipedia article matched this title")
        article = found[0].replace(" ", "_")
        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=89)
        url = (
            "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/"
            f"all-access/user/{httpx.URL(article).path.lstrip('/')}/daily/"
            f"{start:%Y%m%d}/{end:%Y%m%d}"
        )
        r = self.client.get(url, headers=self.headers)
        r.raise_for_status()
        views = [float(item["views"]) for item in r.json()["items"]]
        if len(views) < 14:
            return _unavailable(self.name, "too little pageview history", article=article)
        mean = statistics.mean(views)
        spread = statistics.pstdev(views)
        return SourceEvidence(
            source=self.name,
            status="available",
            freshness_score=0.97,
            quality_score=round(0.6 + 0.4 * min(1.0, len(views) / 90) * min(1.0, found[1]), 3),
            metrics={
                "curiosity": log_scale(mean, 20_000),
                "sustained_interest": clamp(100 * (1 - min(1.0, spread / mean))) if mean else 0.0,
                "mean_daily_views": round(mean, 1),
            },
            warnings=[
                "Wikipedia activity indicates information seeking, not content consumption.",
                *(
                    ["Very low pageviews: the title may have little public footprint, or the matched "
                     "article may be a different work with a similar name."]
                    if mean < 5
                    else []
                ),
            ],
            provenance={
                "mode": "live",
                "article": article,
                "match_similarity": f"{found[1]:.2f}",
                "window": f"{start}..{end}",
                "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
            },
        )


class AniListLive(_HttpAdapter):
    name = "anilist"
    QUERY = """
    query ($s: String) { Page(perPage: 6) { media(search: $s, type: ANIME) {
      id title { romaji english } format genres tags { name } description
      studios { nodes { name } } startDate { year } averageScore popularity favourites
    } } }"""

    def _collect(self, title: Title) -> SourceEvidence:
        best: tuple[dict, float] | None = None
        for query in _candidates(title):
            r = self.client.post(
                "https://graphql.anilist.co",
                json={"query": self.QUERY, "variables": {"s": query}},
                headers=self.headers,
            )
            r.raise_for_status()
            for media in r.json()["data"]["Page"]["media"]:
                names = [n for n in (media["title"]["romaji"], media["title"]["english"]) if n]
                score = max(
                    name_similarity(candidate, name) for candidate in _candidates(title) for name in names
                )
                if best is None or score > best[1]:
                    best = (media, score)
        if best is None or best[1] < MATCH_THRESHOLD:
            return _unavailable(self.name, "no AniList entry matched this title")
        media, match = best
        fields = [
            media["genres"], media["tags"], media["description"], media["studios"]["nodes"],
            media["startDate"]["year"], media["averageScore"],
        ]
        completeness = 100 * sum(bool(f) for f in fields) / len(fields)
        affinity = 0.6 * (media["averageScore"] or 50) + 0.4 * log_scale(media["popularity"] or 0, 1_000_000)
        return SourceEvidence(
            source=self.name,
            status="available",
            freshness_score=0.95,
            quality_score=round(0.55 + 0.45 * match, 3),
            metrics={
                "metadata_completeness": clamp(completeness),
                "historical_affinity": clamp(affinity),
                "average_score": float(media["averageScore"] or 0),
                "popularity": float(media["popularity"] or 0),
            },
            warnings=[],
            provenance={
                "mode": "live",
                "anilist_id": str(media["id"]),
                "matched_title": media["title"]["romaji"] or "",
                "match_similarity": f"{match:.2f}",
                "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
            },
        )


class YouTubeLive(_HttpAdapter):
    name = "youtube"
    BASE = "https://www.googleapis.com/youtube/v3"

    def _collect(self, title: Title) -> SourceEvidence:
        key = self.settings.youtube_api_key
        if not key:
            return _unavailable(self.name, "KIZUNA_YOUTUBE_API_KEY is not configured")
        auth = {"x-goog-api-key": key}  # header, not query string, so the key never lands in logs
        video_id = None
        if title.trailer_url:
            match = re.search(r"(?:v=|youtu\.be/)([\w-]{6,})", str(title.trailer_url))
            video_id = match.group(1) if match else None
        if not video_id:
            r = self.client.get(
                f"{self.BASE}/search",
                params={"part": "snippet", "q": f"{title.name} official trailer", "type": "video",
                        "maxResults": 5},
                headers=auth,
            )
            r.raise_for_status()
            video_id = next(
                (
                    item["id"]["videoId"]
                    for item in r.json().get("items", [])
                    if _title_in_video(title.name, item["snippet"]["title"])
                ),
                None,
            )
        if not video_id:
            return _unavailable(self.name, "no trailer video whose title matches this title")
        r = self.client.get(
            f"{self.BASE}/videos",
            params={"part": "statistics,snippet", "id": video_id},
            headers=auth,
        )
        r.raise_for_status()
        items = r.json().get("items", [])
        if not items:
            return _unavailable(self.name, "trailer video not found", video_id=video_id)
        stats, snippet = items[0]["statistics"], items[0]["snippet"]
        views = float(stats.get("viewCount", 0))
        if views <= 0:
            return _unavailable(self.name, "trailer has no recorded views", video_id=video_id)
        likes, comments = float(stats.get("likeCount", 0)), float(stats.get("commentCount", 0))
        published = datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00"))
        days = max(1.0, (datetime.now(UTC) - published).total_seconds() / 86400)
        return SourceEvidence(
            source=self.name,
            status="available",
            freshness_score=0.95,
            quality_score=0.85,
            metrics={
                "attention": log_scale(views, 50_000_000),
                "engagement_quality": clamp(100 * ((likes + 2 * comments) / views) / 0.06),
                "velocity": log_scale(views / days, 500_000),
                "views": views,
            },
            warnings=["Public YouTube video statistics are global and not exact India-only views."],
            provenance={"mode": "live", "video_id": video_id,
                        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds")},
        )


def combine_state_interest(vectors: list[tuple[str, dict[str, float]]]) -> dict[str, float]:
    """Average several search terms' state vectors (each 0-100, top state = 100).

    `vectors` holds (language, {state: interest}). A term in a state's own language counts double
    there, because that is how people in that state actually search. All-zero vectors are skipped.
    """
    usable = [(lang, vec) for lang, vec in vectors if vec and max(vec.values()) > 0]
    if not usable:
        return {}
    out: dict[str, float] = {}
    for state in STATES:
        total = weight_sum = 0.0
        for lang, vec in usable:
            if state in vec:
                weight = 2.0 if lang == LOCAL_LANG.get(state) else 1.0
                total += weight * vec[state]
                weight_sum += weight
        if weight_sum:
            out[state] = round(total / weight_sum, 2)
    return out if len(out) == len(STATES) else {}


class TrendsLive(SourceAdapter):
    """Google Trends via the optional, unofficial `pytrends` client (India, last 3 months).

    National interest comes from the primary name. State interest averages the primary name, the
    original-script name and native-script names from Wikipedia language links (Hindi, Bengali,
    Tamil, Marathi, Telugu, Kannada, Malayalam), at most MAX_TERMS searches per title.
    """

    name = "google_trends"
    MAX_TERMS = 5
    PAUSE_SECONDS = 1.5

    def __init__(self, client: httpx.Client | None = None, settings: Settings | None = None, factory=None):
        self.client = client
        self.settings = settings
        self.factory = factory  # injectable pytrends-compatible class, for tests

    def _terms(self, title: Title) -> list[tuple[str, str]]:
        """(language, term) pairs, most important first, without duplicates."""
        primary = title.english_title or title.name
        terms = [("en", primary)]
        if title.name.strip().lower() != primary.strip().lower():
            terms.append(("ja", title.name))
        if self.client and self.settings:
            headers = {"User-Agent": f"KizunaSignal/0.2 (+{self.settings.source_contact_url})"}
            try:
                found = resolve_article(self.client, headers, title)
                if found:
                    for lang, term in vernacular_terms(self.client, headers, found[0]).items():
                        terms.append((lang, term))
            except (httpx.HTTPError, ValueError, KeyError):
                pass  # vernacular names are an enhancement; English/original terms still work
        seen: set[str] = set()
        unique = []
        for lang, term in terms:
            if term.lower() not in seen:
                seen.add(term.lower())
                unique.append((lang, term))
        return unique[: self.MAX_TERMS]

    def collect(self, title: Title) -> SourceEvidence:
        if self.factory is None:
            try:
                from pytrends.request import TrendReq
            except ImportError:
                return _unavailable(self.name, "optional package 'pytrends' is not installed")
        else:
            TrendReq = self.factory  # noqa: N806
        global _trends_blocked_until
        if time.time() < _trends_blocked_until:
            return _unavailable(self.name, "Google Trends is rate-limiting requests; retrying later")
        terms = self._terms(title)
        client, frame, error = TrendReq(hl="en-IN", tz=330, timeout=(5, 15)), None, None
        for attempt in range(2):  # one retry: the unofficial endpoint intermittently answers 429
            try:
                client.build_payload([terms[0][1]], geo="IN", timeframe="today 3-m")
                frame = client.interest_over_time()
                break
            except Exception as exc:  # noqa: BLE001 - unofficial client raises assorted errors
                error = exc
                time.sleep(2 * (attempt + 1))
        if frame is None:
            _trends_blocked_until = time.time() + 900
            return _unavailable(self.name, f"Google Trends request failed ({type(error).__name__})")
        if frame.empty:
            return _unavailable(self.name, "no Google Trends data for this term")
        series = [float(v) for v in frame.iloc[:, 0]]
        mean = statistics.mean(series)
        if mean == 0:
            return _unavailable(self.name, "search interest too low to measure")
        recent, prior = statistics.mean(series[-4:]), statistics.mean(series[:-4]) or 1.0
        vectors: list[tuple[str, dict[str, float]]] = []
        used_terms = []
        for index, (lang, term) in enumerate(terms):
            if index:
                time.sleep(self.PAUSE_SECONDS)
                try:
                    client.build_payload([term], geo="IN", timeframe="today 3-m")
                except Exception:  # noqa: BLE001 - skip a term that cannot be queried
                    continue
            vector = _TrendsStates.fetch(client)
            if vector:
                vectors.append((lang, vector))
                used_terms.append(f"{lang}:{term}")
        by_state = combine_state_interest(vectors)
        return SourceEvidence(
            source=self.name,
            status="available",
            freshness_score=0.9,
            quality_score=0.7,
            metrics={
                "relative_interest": clamp(mean),
                "momentum": clamp(50 + 50 * (recent - prior) / prior),
                "stability": clamp(100 * (1 - min(1.0, statistics.pstdev(series) / mean))),
                **{f"state_interest_{state}": value for state, value in by_state.items()},
                "state_terms_used": float(len(used_terms)),
            },
            warnings=[
                "Google Trends values are normalized relative interest, not absolute volume.",
                *(["Very low search interest; the term may be unrelated to this title."] if mean < 5 else []),
            ],
            provenance={"mode": "live", "geo": "IN", "timeframe": "today 3-m",
                        "client": "pytrends (unofficial)",
                        "terms": " | ".join(used_terms),
                        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds")},
        )


class _TrendsStates:
    GOOGLE_REGION = {"Delhi NCR": "Delhi"}

    @staticmethod
    def fetch(client) -> dict[str, float]:
        """Relative search interest (0-100, top region = 100) for the eight modelled states."""
        try:
            frame = client.interest_by_region(resolution="REGION", inc_low_vol=True, inc_geo_code=False)
        except Exception:  # noqa: BLE001 - best effort; the national series is still used
            return {}
        out: dict[str, float] = {}
        for state in STATES:
            region = _TrendsStates.GOOGLE_REGION.get(state, state)
            if region in frame.index:
                out[state] = float(frame.loc[region].iloc[0])
        return out if len(out) == len(STATES) else {}


class RegionalContextCensus(SourceAdapter):
    """Language coverage and digital-reach index from the Census 2011 state figures."""

    name = "regional_context"

    def collect(self, title: Title) -> SourceEvidence:
        wanted = {lang.lower() for lang in title.target_languages}
        population = {s: CENSUS[s]["population_m"] for s in STATES}
        total = sum(population.values())
        covered = sum(population[s] for s in STATES if STATE_LANGUAGE[s] in wanted)
        language_fit = 100 * covered / total
        focus = [s for s in title.target_states if s in population] or list(STATES)
        reach = {s: CENSUS[s]["urban_pct"] * CENSUS[s]["literacy_pct"] for s in STATES}
        top = max(reach.values())
        weight = sum(population[s] for s in focus)
        market = 100 * sum(population[s] * reach[s] / top for s in focus) / weight
        warnings = ["Census 2011 figures are approximate and predate current streaming reach."]
        if not wanted:
            warnings.append("No target language supplied; language fit is 0.")
        return SourceEvidence(
            source=self.name,
            status="available",
            freshness_score=0.5,
            quality_score=0.7,
            metrics={"language_fit": clamp(language_fit), "addressable_market": clamp(market)},
            warnings=warnings,
            provenance={"mode": "census-2011-derived", "states_modelled": str(len(STATES))},
        )


DISK_TTL_SECONDS = 24 * 3600


class _DiskCache:
    """Per-title evidence persisted for 24h so reruns are stable and rate-limited sources
    (notably unofficial Google Trends) are not hammered. Only successful results are stored."""

    def __init__(self, directory: str | None):
        self.directory = Path(directory) if directory else None

    def _path(self, name: str, title: Title) -> Path:
        key = hashlib.sha256(f"{name}|{title.name}|{title.english_title}".encode()).hexdigest()[:20]
        return self.directory / f"{name}_{key}.json"  # type: ignore[operator]

    def get(self, name: str, title: Title) -> SourceEvidence | None:
        if not self.directory:
            return None
        path = self._path(name, title)
        if not path.exists() or time.time() - path.stat().st_mtime > DISK_TTL_SECONDS:
            return None
        try:
            return replace(SourceEvidence(**json.loads(path.read_text(encoding="utf-8"))), status="cached")
        except (ValueError, TypeError):
            return None

    def put(self, name: str, title: Title, evidence: SourceEvidence) -> None:
        if self.directory and evidence.status in {"available", "cached"}:
            self.directory.mkdir(parents=True, exist_ok=True)
            self._path(name, title).write_text(json.dumps(asdict(evidence)), encoding="utf-8")


class LiveSourceRegistry:
    SOURCE_NAMES = ("google_trends", "youtube", "wikimedia", "anilist", "regional_context")

    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self.client = client or httpx.Client(timeout=httpx.Timeout(10.0), follow_redirects=True)
        self.disk = _DiskCache(settings.source_cache_dir)
        self.adapters: dict[str, SourceAdapter] = {
            "google_trends": TrendsLive(self.client, settings),
            "youtube": YouTubeLive(self.client, settings),
            "wikimedia": WikimediaLive(self.client, settings),
            "anilist": AniListLive(self.client, settings),
            "regional_context": RegionalContextCensus(),
        }

    def collect(self, title: Title, disabled_sources: set[str] | None = None) -> list[SourceEvidence]:
        disabled = disabled_sources or set()
        results = []
        for name in self.SOURCE_NAMES:
            if name in disabled:
                results.append(_unavailable(name, "disabled for this run"))
                continue
            if name != "regional_context" and (hit := self.disk.get(name, title)):
                results.append(hit)
                continue
            try:
                evidence = self.adapters[name].collect(title)
                self.disk.put(name, title, evidence)
                results.append(evidence)
            except Exception as exc:  # noqa: BLE001 - one source must never fail the analysis
                results.append(_unavailable(name, f"unexpected error ({type(exc).__name__})"))
        return results
