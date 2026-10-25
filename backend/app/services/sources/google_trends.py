from __future__ import annotations

import logging
import math
import statistics
import time
from collections.abc import Callable
from typing import Any

from app.db.models import Title
from app.services.census import resolve_state
from app.services.sources.base import MALFORMED_RESPONSE_ERRORS, SourceAdapter, SourceEvidence
from app.services.sources.vernacular import combine_state_interest

logger = logging.getLogger(__name__)

TIMEFRAME = "today 3-m"
RECENT_DAYS = 30
MOMENTUM_WINDOW = 14


def _reason(exc: Exception) -> str:
    """Text safe to show in warnings: parse failures are described, not echoed."""
    if isinstance(exc, MALFORMED_RESPONSE_ERRORS):
        return "unexpected response format"
    return str(exc)


class TrendsError(Exception):
    pass


class TrendsRateLimited(TrendsError):
    pass


def default_trends_factory(timeout: float) -> Any:
    from pytrends.request import TrendReq

    return TrendReq(hl="en-IN", tz=330, timeout=(min(5.0, timeout), timeout))


class GoogleTrendsAdapter(SourceAdapter):
    """Google Trends interest via pytrends (unofficial scraper, so rate limits are expected).

    Trends only reports values relative to the busiest term in the request, so the title is
    queried together with a benchmark term; relative_interest compares the title to that anchor.
    """

    name = "google_trends"
    # query -> (fetched_at, evidence); shared across requests to stay well under Google's limits.
    _cache: dict[tuple[str, str], tuple[float, SourceEvidence]] = {}
    _blocked_until: float = 0.0

    def __init__(
        self,
        geo: str = "IN",
        benchmark: str = "One Piece",
        timeout: float = 10.0,
        cache_ttl_seconds: int = 6 * 3600,
        cooldown_seconds: int = 15 * 60,
        trends_factory: Callable[[], Any] | None = None,
        clock: Callable[[], float] = time.monotonic,
        term_provider: Callable[[Title], list[tuple[str, str]]] | None = None,
        max_terms: int = 4,
        pause_seconds: float = 1.5,
    ):
        self.geo = geo
        self.benchmark = benchmark
        self.cache_ttl_seconds = cache_ttl_seconds
        self.cooldown_seconds = cooldown_seconds
        self.trends_factory = trends_factory or (lambda: default_trends_factory(timeout))
        self.clock = clock
        # (language code, native-script name) pairs searched in addition to the main keyword.
        self.term_provider = term_provider
        self.max_terms = max(1, max_terms)
        self.pause_seconds = pause_seconds

    def collect(self, title: Title) -> SourceEvidence:
        keyword = (title.english_title or title.name).strip()
        key = (keyword.casefold(), self.geo)
        now = self.clock()
        cached = self._cache.get(key)
        if cached and now - cached[0] < self.cache_ttl_seconds:
            return self._as_cached(cached[1])
        if now < GoogleTrendsAdapter._blocked_until:
            wait = int(GoogleTrendsAdapter._blocked_until - now)
            return self._unavailable(
                title, f"Google Trends is rate limiting this server; retrying in ~{wait}s."
            )
        try:
            evidence = self._collect(title, keyword)
        except TrendsRateLimited:
            GoogleTrendsAdapter._blocked_until = now + self.cooldown_seconds
            logger.warning("google_trends_rate_limited", extra={"title": title.name})
            return self._unavailable(
                title, "Google Trends rate limit reached; interest not measured for now."
            )
        except Exception as exc:  # pytrends raises assorted requests/pandas errors
            logger.warning(
                "google_trends_unavailable", extra={"title": title.name, "error": str(exc)}
            )
            return self._unavailable(title, f"Google Trends request failed: {_reason(exc)}")
        if evidence.status == "available" and evidence.regional:
            self._cache[key] = (now, evidence)  # skip caching when the state split failed
        return evidence

    def _collect(self, title: Title, keyword: str) -> SourceEvidence:
        use_benchmark = self.benchmark.casefold() != keyword.casefold()
        terms = [keyword, self.benchmark] if use_benchmark else [keyword]
        frame = self._fetch(terms)
        if frame is None or keyword not in frame.columns or len(frame) < RECENT_DAYS:
            return self._unavailable(title, "Google Trends returned no usable data for this title.")

        series = [float(v) for v in frame[keyword]]
        recent = series[-RECENT_DAYS:]
        recent_mean = statistics.mean(recent)
        if recent_mean == 0 and not any(series):
            return self._unavailable(
                title, "Google Trends reports no search interest for this title in India."
            )

        if use_benchmark:
            bench_mean = statistics.mean(
                float(v) for v in frame[self.benchmark].iloc[-RECENT_DAYS:]
            )
            ratio = recent_mean / bench_mean if bench_mean else 1.0
            relative = min(100.0, 100 * math.sqrt(ratio))
        else:
            relative = recent_mean
        latest = statistics.mean(series[-MOMENTUM_WINDOW:])
        prior = statistics.mean(series[-2 * MOMENTUM_WINDOW : -MOMENTUM_WINDOW])
        if prior > 0:
            momentum = 50 + 50 * math.tanh(latest / prior - 1)
        else:
            momentum = 90.0 if latest > 0 else 50.0
        mean_all = statistics.mean(series)
        cv = statistics.pstdev(series) / mean_all if mean_all else 1.0
        stability = 100 * (1 - min(1.0, cv))

        warnings = ["Google Trends values are normalized relative interest, not absolute volume."]
        regional: dict[str, dict[str, float]] = {}
        try:
            regional = self._fetch_regions(keyword)
        except TrendsRateLimited:
            GoogleTrendsAdapter._blocked_until = self.clock() + self.cooldown_seconds
            warnings.append("State-level Google Trends interest skipped: rate limit reached.")
        except Exception as exc:  # the national signal is still valid without the state split
            logger.warning("google_trends_regions_failed", extra={"error": str(exc)})
            warnings.append(f"State-level Google Trends interest unavailable: {_reason(exc)}")
        else:
            if not regional:
                warnings.append("Google Trends returned no state-level interest for this title.")
        terms_used = [f"en:{keyword}"]
        if regional:
            regional, extra_terms = self._add_native_terms(title, regional, warnings)
            terms_used.extend(extra_terms)

        return SourceEvidence(
            source=self.name,
            status="available",
            freshness_score=1.0,
            quality_score=round(min(1.0, len(series) / 85), 2),
            metrics={
                "relative_interest": round(relative, 2),
                "momentum": round(momentum, 2),
                "stability": round(stability, 2),
                "avg_interest_30d": round(recent_mean, 2),
            },
            warnings=warnings,
            regional=regional,
            provenance={
                "mode": "live",
                "api": "pytrends-unofficial",
                "regions": str(len(regional)),
                "geo": self.geo,
                "timeframe": TIMEFRAME,
                "keyword": keyword,
                "terms": " | ".join(terms_used),
                "benchmark": self.benchmark if use_benchmark else "none",
            },
        )

    def _add_native_terms(
        self, title: Title, regional: dict[str, dict[str, float]], warnings: list[str]
    ) -> tuple[dict[str, dict[str, float]], list[str]]:
        """Fold native-script searches into the state split (best effort; never fails the source)."""
        if self.term_provider is None:
            return regional, []
        try:
            terms = self.term_provider(title)[: self.max_terms - 1]
        except Exception as exc:  # noqa: BLE001 - native names are an enrichment only
            logger.warning("trends_native_terms_failed", extra={"error": str(exc)})
            return regional, []
        vectors = [("en", {state: v["interest"] for state, v in regional.items()})]
        used: list[str] = []
        for lang, term in terms:
            if self.pause_seconds:
                time.sleep(self.pause_seconds)
            try:
                extra = self._fetch_regions(term)
            except TrendsRateLimited:
                GoogleTrendsAdapter._blocked_until = self.clock() + self.cooldown_seconds
                warnings.append("Native-script Google Trends searches skipped: rate limit reached.")
                break
            except Exception as exc:  # noqa: BLE001 - skip a term that cannot be queried
                logger.warning("trends_native_term_failed", extra={"term": term, "error": str(exc)})
                continue
            if extra:
                vectors.append((lang, {state: v["interest"] for state, v in extra.items()}))
                used.append(f"{lang}:{term}")
        if not used:
            return regional, []
        combined = combine_state_interest(vectors)
        return {state: {"interest": value} for state, value in combined.items()}, used

    def _fetch_regions(self, keyword: str) -> dict[str, dict[str, float]]:
        """Per-state interest (0-100, top state = 100) keyed by canonical Census state name."""
        try:
            client = self.trends_factory()
            client.build_payload([keyword], timeframe=TIMEFRAME, geo=self.geo)
            frame = client.interest_by_region(resolution="REGION", inc_low_vol=True)
        except Exception as exc:
            if "429" in str(exc) or "TooManyRequests" in type(exc).__name__:
                raise TrendsRateLimited(str(exc)) from exc
            raise
        regional: dict[str, dict[str, float]] = {}
        if frame is None or frame.empty or keyword not in frame.columns:
            return regional
        for name, value in frame[keyword].items():
            state = resolve_state(str(name))
            if state is not None:
                regional[state.name] = {"interest": float(value)}
        return regional

    def _fetch(self, terms: list[str]) -> Any:
        try:
            client = self.trends_factory()
            client.build_payload(terms, timeframe=TIMEFRAME, geo=self.geo)
            frame = client.interest_over_time()
        except Exception as exc:
            if "429" in str(exc) or "TooManyRequests" in type(exc).__name__:
                raise TrendsRateLimited(str(exc)) from exc
            raise
        if frame is None or frame.empty:
            return None
        if "isPartial" in frame.columns:
            frame = frame[~frame["isPartial"].astype(bool)]
        return frame

    @staticmethod
    def _as_cached(evidence: SourceEvidence) -> SourceEvidence:
        return SourceEvidence(
            source=evidence.source,
            status="cached",
            freshness_score=0.82,
            quality_score=evidence.quality_score,
            metrics=dict(evidence.metrics),
            warnings=list(evidence.warnings),
            provenance={**evidence.provenance, "cache": "hit"},
            regional={k: dict(v) for k, v in evidence.regional.items()},
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
