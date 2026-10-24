from __future__ import annotations

import logging
import math
import statistics
import time
from collections.abc import Callable
from datetime import UTC, datetime

import httpx

from app.db.models import Title
from app.services.sources.base import SourceAdapter, SourceEvidence
from app.services.textmatch import normalise as _normalise

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
MAX_RESULTS = 10
MIN_TOTAL_VIEWS = 1_000
# Scale ceilings: 100M total views, 100k views/day and a 6% like+comment rate each map to 100.
LOG_VIEWS_CEILING = 8.0
LOG_VELOCITY_CEILING = 5.0
ENGAGEMENT_CEILING = 0.06


class YouTubeError(Exception):
    pass


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class YouTubeAdapter(SourceAdapter):
    """Public YouTube trailer/video statistics via the Data API v3 (API key, no OAuth)."""

    name = "youtube"
    # query -> (fetched_at, evidence); shared so repeat analyses don't spend search quota.
    _cache: dict[str, tuple[float, SourceEvidence]] = {}

    def __init__(
        self,
        client: httpx.Client,
        api_key: str,
        cache_ttl_seconds: int = 6 * 3600,
        now: Callable[[], datetime] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.client = client
        # Sent as a header, never in the URL, so httpx request logging cannot leak it.
        self.headers = {"x-goog-api-key": api_key}
        self.cache_ttl_seconds = cache_ttl_seconds
        self.now = now or (lambda: datetime.now(UTC))
        self.clock = clock

    def collect(self, title: Title) -> SourceEvidence:
        query_name = title.english_title or title.name
        cached = self._cache.get(_normalise(query_name))
        if cached and self.clock() - cached[0] < self.cache_ttl_seconds:
            return self._as_cached(cached[1])
        try:
            evidence = self._collect(title, query_name)
        except (httpx.HTTPError, YouTubeError, KeyError, ValueError) as exc:
            logger.warning("youtube_unavailable", extra={"title": title.name, "error": str(exc)})
            return self._unavailable(title, f"YouTube request failed: {exc}")
        if evidence.status == "available":
            self._cache[_normalise(query_name)] = (self.clock(), evidence)
        return evidence

    def _collect(self, title: Title, query_name: str) -> SourceEvidence:
        search = self._get(
            SEARCH_URL,
            {
                "part": "id",
                "q": f"{query_name} official trailer",
                "type": "video",
                "maxResults": MAX_RESULTS,
                "regionCode": "IN",
                "safeSearch": "none",
            },
        )
        ids = [item["id"]["videoId"] for item in search.get("items", []) if "videoId" in item["id"]]
        if not ids:
            return self._unavailable(title, "No YouTube videos found for this title.")

        videos = self._get(VIDEOS_URL, {"part": "snippet,statistics", "id": ",".join(ids)}).get(
            "items", []
        )
        wanted = _normalise(query_name)
        relevant = [v for v in videos if wanted in _normalise(v["snippet"]["title"])]
        if not relevant:
            return self._unavailable(
                title, "YouTube results did not clearly match this title; interest not measured."
            )

        now = self.now()
        views = likes = comments = 0
        velocity = 0.0
        for video in relevant:
            stats = video["statistics"]
            v = int(stats.get("viewCount", 0))
            views += v
            likes += int(stats.get("likeCount", 0))
            comments += int(stats.get("commentCount", 0))
            age_days = max(1.0, (now - _parse_time(video["snippet"]["publishedAt"])).days)
            velocity += v / age_days
        if views < MIN_TOTAL_VIEWS:
            return self._unavailable(
                title,
                "No meaningful YouTube footprint for this title (matched videos have under "
                f"{MIN_TOTAL_VIEWS:,} views in total, likely unrelated); interest not measured.",
            )

        attention = min(100.0, 100 * math.log10(views + 1) / LOG_VIEWS_CEILING)
        engagement = min(100.0, 100 * ((likes + comments) / views) / ENGAGEMENT_CEILING)
        velocity_score = min(100.0, 100 * math.log10(velocity + 1) / LOG_VELOCITY_CEILING)
        median_views = statistics.median(int(v["statistics"].get("viewCount", 0)) for v in relevant)

        return SourceEvidence(
            source=self.name,
            status="available",
            freshness_score=1.0,
            quality_score=round(min(1.0, 0.4 + 0.12 * len(relevant)), 2),
            metrics={
                "attention": round(attention, 2),
                "engagement_quality": round(engagement, 2),
                "velocity": round(velocity_score, 2),
                "total_views": float(views),
                "matched_videos": float(len(relevant)),
                "median_video_views": float(median_views),
            },
            warnings=["Public YouTube video statistics are global and not exact India-only views."],
            provenance={
                "mode": "live",
                "api": "youtube-data-api-v3",
                "query": f"{query_name} official trailer",
                "videos": ",".join(v["id"] for v in relevant),
                "region_bias": "IN",
            },
        )

    def _get(self, url: str, params: dict) -> dict:
        response = self.client.get(url, params=params, headers=self.headers)
        if response.status_code == 403:
            reason = ""
            try:
                reason = response.json()["error"]["errors"][0]["reason"]
            except (KeyError, IndexError, ValueError):
                pass
            raise YouTubeError(f"access denied ({reason or 'forbidden'}); check key and quota")
        if response.status_code != 200:
            raise YouTubeError(f"HTTP {response.status_code}")
        return response.json()

    @staticmethod
    def _as_cached(evidence: SourceEvidence) -> SourceEvidence:
        return SourceEvidence(
            source=evidence.source,
            status="cached",
            freshness_score=0.85,
            quality_score=evidence.quality_score,
            metrics=dict(evidence.metrics),
            warnings=list(evidence.warnings),
            provenance={**evidence.provenance, "cache": "hit"},
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
