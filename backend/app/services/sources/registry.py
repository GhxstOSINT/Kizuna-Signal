from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import httpx

from app.core.config import Settings, get_settings
from app.db.models import Title
from app.services.sources.anilist import AniListAdapter
from app.services.sources.base import SourceAdapter, SourceEvidence
from app.services.sources.demo import DemoAdapter
from app.services.sources.google_trends import GoogleTrendsAdapter
from app.services.sources.regional_context import RegionalContextAdapter
from app.services.sources.wikimedia import WikimediaAdapter
from app.services.sources.youtube import YouTubeAdapter
from app.services.survey import SurveyData

logger = logging.getLogger(__name__)

SOURCE_NAMES = (
    "google_trends",
    "youtube",
    "wikimedia",
    "anilist",
    "regional_context",
)

# Live-mode adapters. In demo mode every source uses the deterministic offline DemoAdapter; in
# live mode a source is either one of these or reported unavailable. It never falls back to demo
# numbers, because synthetic evidence in a real analysis would be fabrication.
LiveFactory = Callable[[httpx.Client, Settings], SourceAdapter]
LIVE_ADAPTERS: dict[str, LiveFactory] = {
    "google_trends": lambda client, settings: GoogleTrendsAdapter(
        geo=settings.trends_geo,
        benchmark=settings.trends_benchmark,
        timeout=settings.source_timeout_seconds,
        cache_ttl_seconds=settings.trends_cache_ttl_seconds,
        cooldown_seconds=settings.trends_cooldown_seconds,
    ),
    "wikimedia": lambda client, settings: WikimediaAdapter(
        client, lookback_days=settings.wikimedia_lookback_days
    ),
    "youtube": lambda client, settings: YouTubeAdapter(
        client, settings.youtube_api_key, cache_ttl_seconds=settings.youtube_cache_ttl_seconds
    ),
    "anilist": lambda client, settings: AniListAdapter(
        client,
        cache_ttl_seconds=settings.anilist_cache_ttl_seconds,
        cooldown_seconds=settings.anilist_cooldown_seconds,
    ),
    "regional_context": lambda client, settings: RegionalContextAdapter(
        SurveyData.from_dir(settings.survey_dir)
    ),
}
# Live adapters that need configuration; when it is missing the source is reported unconfigured.
LIVE_REQUIREMENTS: dict[str, tuple[Callable[[Settings], bool], str]] = {
    "youtube": (lambda settings: bool(settings.youtube_api_key), "KIZUNA_YOUTUBE_API_KEY"),
}


class SourceRegistry:
    SOURCE_NAMES = SOURCE_NAMES

    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None):
        self.settings = settings or get_settings()
        self._client = client

    def mode_for(self, name: str) -> str:
        """'demo' (offline synthetic), 'live', or 'unconfigured' (live mode, missing config)."""
        if self.settings.demo_mode:
            return "demo"
        requirement = LIVE_REQUIREMENTS.get(name)
        if name not in LIVE_ADAPTERS or (requirement and not requirement[0](self.settings)):
            return "unconfigured"
        return "live"

    def collect(
        self, title: Title, disabled_sources: set[str] | None = None
    ) -> list[SourceEvidence]:
        disabled_sources = disabled_sources or set()
        owns_client = self._client is None
        client = self._client or httpx.Client(
            timeout=self.settings.source_timeout_seconds,
            headers={"User-Agent": self.settings.source_user_agent},
            follow_redirects=True,
            # Wikimedia's edge answers 403 to httpx over HTTP/1.1 but accepts HTTP/2.
            http2=True,
        )
        try:
            with ThreadPoolExecutor(max_workers=len(self.SOURCE_NAMES)) as pool:
                futures = [
                    pool.submit(self._collect_one, name, title, client, disabled_sources)
                    for name in self.SOURCE_NAMES
                ]
                return [future.result() for future in futures]
        finally:
            if owns_client:
                client.close()

    def _collect_one(
        self, name: str, title: Title, client: httpx.Client, disabled_sources: set[str]
    ) -> SourceEvidence:
        if name in disabled_sources:
            return DemoAdapter(name, "unavailable").collect(title)
        mode = self.mode_for(name)
        if mode == "demo":
            if name == "regional_context":  # offline Census + the labelled synthetic survey
                return RegionalContextAdapter(
                    SurveyData.from_dir(self.settings.survey_dir)
                ).collect(title)
            return DemoAdapter(name).collect(title)
        if mode == "unconfigured":
            return self._unavailable(name, title, f"{name} is not configured; no data was used.")
        try:
            return LIVE_ADAPTERS[name](client, self.settings).collect(title)
        except Exception:  # one broken source must not fail the whole analysis
            logger.exception("source_failed", extra={"source": name})
            return self._unavailable(name, title, f"{name} failed unexpectedly; no data was used.")

    @staticmethod
    def _unavailable(name: str, title: Title, warning: str) -> SourceEvidence:
        return SourceEvidence(
            source=name,
            status="unavailable",
            freshness_score=0.0,
            quality_score=0.0,
            warnings=[warning],
            provenance={"mode": "unavailable", "title": title.name},
        )
