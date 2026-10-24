from __future__ import annotations

import logging
import math
import statistics
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from urllib.parse import quote

import httpx

from app.db.models import Title
from app.services.sources.base import MALFORMED_RESPONSE_ERRORS, SourceAdapter, SourceEvidence
from app.services.textmatch import match_score

logger = logging.getLogger(__name__)

SEARCH_URL = "https://{lang}.wikipedia.org/w/rest.php/v1/search/title"
PAGEVIEWS_URL = (
    "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
    "{lang}.wikipedia/all-access/user/{article}/daily/{start}/{end}"
)
MIN_MATCH = 0.85
CONFIDENT_MATCH = 0.9
RECENT_WINDOW_DAYS = 30
# ~10k daily views on a title's article is treated as the ceiling of the 0-100 curiosity scale.
LOG_VIEWS_CEILING = 4.0


class WikimediaError(Exception):
    pass


def _is_disambiguation(page: dict) -> bool:
    description = (page.get("description") or "").casefold()
    return "disambiguation" in description or "referred to by the same" in description


class WikimediaAdapter(SourceAdapter):
    """Wikipedia article page views as a proxy for information-seeking interest."""

    name = "wikimedia"

    def __init__(
        self,
        client: httpx.Client,
        lookback_days: int = 90,
        today: Callable[[], date] | None = None,
    ):
        self.client = client
        self.lookback_days = max(RECENT_WINDOW_DAYS + 1, lookback_days)
        self.today = today or (lambda: datetime.now(UTC).date())

    def collect(self, title: Title) -> SourceEvidence:
        try:
            return self._collect(title)
        except (httpx.HTTPError, WikimediaError, ValueError) as exc:
            logger.warning("wikimedia_unavailable", extra={"title": title.name, "error": str(exc)})
            return self._unavailable(title, f"Wikimedia request failed: {exc}")
        except MALFORMED_RESPONSE_ERRORS as exc:
            logger.warning("wikimedia_malformed", extra={"title": title.name, "error": repr(exc)})
            return self._unavailable(
                title, "Wikimedia returned a response in an unexpected format."
            )

    def _collect(self, title: Title) -> SourceEvidence:
        end = self.today() - timedelta(days=1)
        start = end - timedelta(days=self.lookback_days - 1)

        articles = []
        for lang, queries in self._queries(title).items():
            found = self._best_article(lang, queries)
            if found is not None:
                articles.append(found)
        if not articles:
            return self._unavailable(
                title, "No confident Wikipedia article match for this title; interest not measured."
            )

        series: list[dict[str, int]] = []
        used = []
        for lang, key, page_title, score in articles:
            daily = self._pageviews(lang, key, start, end)
            if daily:
                series.append(daily)
                used.append((lang, key, page_title, score))
        if not series:
            return self._unavailable(
                title, "Matched Wikipedia articles returned no page-view data."
            )

        days = [(start + timedelta(days=i)) for i in range(self.lookback_days)]
        totals = [sum(s.get(d.strftime("%Y%m%d"), 0) for s in series) for d in days]
        recent = totals[-RECENT_WINDOW_DAYS:]
        recent_mean = statistics.mean(recent)
        median = statistics.median(totals)
        steady_days = sum(1 for v in totals if v >= 0.5 * median) / len(totals) if median else 0.0

        curiosity = min(100.0, 100 * math.log10(recent_mean + 1) / LOG_VIEWS_CEILING)
        sustained = 100 * steady_days
        coverage = max(len(s) for s in series) / self.lookback_days
        worst_match = min(score for *_, score in used)

        warnings = ["Wikipedia activity indicates information seeking, not content consumption."]
        if worst_match < CONFIDENT_MATCH:
            matched = "; ".join(f"{lang}:{page_title}" for lang, _, page_title, _ in used)
            warnings.append(
                f"Wikipedia article match is approximate ({matched}); verify it is the right title."
            )
        if coverage < 0.8:
            warnings.append(
                "Wikipedia page-view history is short; the article may be new or recently renamed."
            )

        return SourceEvidence(
            source=self.name,
            status="available",
            freshness_score=1.0,
            quality_score=round(min(1.0, 0.5 * worst_match + 0.5 * min(1.0, coverage)), 2),
            metrics={
                "curiosity": round(curiosity, 2),
                "sustained_interest": round(sustained, 2),
                "avg_daily_views_30d": round(recent_mean, 1),
            },
            warnings=warnings,
            provenance={
                "mode": "live",
                "api": "wikimedia-pageviews-rest-v1",
                "articles": ", ".join(f"{lang}:{key}" for lang, key, _, _ in used),
                "window": f"{start.isoformat()}..{end.isoformat()}",
                "agent": "user",
            },
        )

    @staticmethod
    def _queries(title: Title) -> dict[str, list[str]]:
        queries: dict[str, list[str]] = {"en": []}
        for candidate in (title.english_title, title.name):
            if candidate and candidate not in queries["en"]:
                queries["en"].append(candidate)
        if title.name and not title.name.isascii():
            queries["ja"] = [title.name]
        return queries

    def _best_article(self, lang: str, queries: list[str]) -> tuple[str, str, str, float] | None:
        best: tuple[str, str, str, float] | None = None
        for query in queries:
            response = self.client.get(
                SEARCH_URL.format(lang=lang), params={"q": query, "limit": 5}
            )
            if response.status_code != 200:
                raise WikimediaError(f"search returned HTTP {response.status_code}")
            for page in response.json().get("pages", []):
                if _is_disambiguation(page):
                    continue
                score = match_score(query, page.get("title", ""))
                if score >= MIN_MATCH and (best is None or score > best[3]):
                    best = (lang, page["key"], page["title"], score)
        return best

    def _pageviews(self, lang: str, key: str, start: date, end: date) -> dict[str, int]:
        url = PAGEVIEWS_URL.format(
            lang=lang,
            article=quote(key, safe=""),
            start=start.strftime("%Y%m%d"),
            end=end.strftime("%Y%m%d"),
        )
        response = self.client.get(url)
        if response.status_code == 404:
            return {}
        if response.status_code != 200:
            raise WikimediaError(f"pageviews returned HTTP {response.status_code}")
        return {item["timestamp"][:8]: int(item["views"]) for item in response.json()["items"]}

    def _unavailable(self, title: Title, warning: str) -> SourceEvidence:
        return SourceEvidence(
            source=self.name,
            status="unavailable",
            freshness_score=0.0,
            quality_score=0.0,
            warnings=[warning],
            provenance={"mode": "live", "title": title.name},
        )
