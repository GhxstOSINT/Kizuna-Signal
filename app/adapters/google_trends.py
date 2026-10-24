"""Google Trends source adapter (India, state level).

Values are relative search interest (0-100) *within one request*, so every request
pairs the title with a fixed anchor term; ratios to the anchor are comparable
across titles. Search interest is curiosity, not consumption.
"""

import hashlib
import json
import random
import time
from datetime import UTC, date, datetime
from pathlib import Path

from app.core.config import settings


class TrendsError(RuntimeError):
    pass


class RateLimited(TrendsError):
    pass


class GeoUnsupported(TrendsError):
    """Google answers HTTP 400 for this region code; retrying cannot help."""


class QuotaExceeded(TrendsError):
    pass


class PytrendsFetcher:
    """Live fetcher. Returns [{"date", "values": {term: int}, "partial"}] (weekly)."""

    def __init__(self):
        from pytrends.request import TrendReq

        self._trend = TrendReq(hl="en-IN", tz=330, timeout=(10, 30))

    def __call__(self, terms: list[str], geo: str, start: date, end: date) -> list[dict]:
        from pytrends.exceptions import TooManyRequestsError

        try:
            self._trend.build_payload(terms, geo=geo, timeframe=f"{start} {end}")
            frame = self._trend.interest_over_time()
        except TooManyRequestsError as exc:
            raise RateLimited(str(exc)) from exc
        except Exception as exc:  # pytrends raises ResponseError / requests errors
            if "429" in str(exc):
                raise RateLimited(str(exc)) from exc
            if "code 400" in str(exc):
                raise GeoUnsupported(geo) from exc
            raise TrendsError(str(exc)) from exc
        if frame.empty:
            return []
        return [
            {
                "date": idx.date().isoformat(),
                "values": {t: int(row[t]) for t in terms},
                "partial": bool(row.get("isPartial", False)),
            }
            for idx, row in frame.iterrows()
        ]


class TrendsClient:
    def __init__(
        self,
        fetcher=None,
        raw_dir: Path | None = None,
        max_requests: int | None = None,
        sleep=time.sleep,
    ):
        self.fetcher = fetcher or PytrendsFetcher()
        self.raw_dir = Path(raw_dir or settings.trends_raw_dir)
        self.max_requests = settings.trends_max_requests if max_requests is None else max_requests
        self.live_requests = 0
        self.unsupported: set[str] = set()
        self.rate_limit_hits = 0  # consecutive 429s; resets on success
        self._sleep = sleep

    @staticmethod
    def _key(terms: list[str], geo: str, start: date, end: date) -> str:
        blob = json.dumps([terms, geo, str(start), str(end)])
        return hashlib.sha256(blob.encode()).hexdigest()[:16]

    def fetch(self, term: str, geo: str, start: date, end: date, anchor: str | None = None) -> dict:
        """Interest for `term` vs the anchor over [start, end]. Past windows never change, so
        a cached response is reused indefinitely. Returns the raw envelope."""
        anchor = anchor or settings.trends_anchor
        terms = [term, anchor]
        key = self._key(terms, geo, start, end)
        folder = self.raw_dir / key
        cached = sorted(folder.glob("*.json")) if folder.exists() else []
        if cached:
            return {**json.loads(cached[-1].read_text(encoding="utf-8")), "from_cache": True}

        rows = self._fetch_with_retry(terms, geo, start, end)
        envelope = {
            "source": "google_trends",
            "terms": terms,
            "geo": geo,
            "start": str(start),
            "end": str(end),
            "collected_at": datetime.now(UTC).isoformat(),
            "checksum": hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest(),
            "scale": "relative 0-100 within request; anchor-normalised downstream",
            "rows": rows,
        }
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{envelope['checksum']}.json").write_text(json.dumps(envelope), encoding="utf-8")
        return {**envelope, "from_cache": False}

    def _pause(self) -> None:
        """Jittered spacing looks less like a bot than a fixed beat."""
        self._sleep(settings.trends_delay_s * random.uniform(0.7, 1.6))

    def _fetch_with_retry(self, terms, geo, start, end) -> list[dict]:
        if geo in self.unsupported:
            raise GeoUnsupported(geo)
        if self.live_requests >= self.max_requests:
            raise QuotaExceeded(
                f"request budget of {self.max_requests} used; resume later (cache is kept)"
            )
        last: Exception | None = None
        for attempt in range(settings.trends_max_retries + 1):
            self.live_requests += 1
            try:
                rows = self.fetcher(terms, geo, start, end)
                self.rate_limit_hits = 0
                self._pause()
                return rows
            except GeoUnsupported:
                self.unsupported.add(geo)
                self._pause()
                raise
            except RateLimited as exc:
                last = exc
                self.rate_limit_hits += 1
                if self.rate_limit_hits >= settings.trends_circuit_breaker:
                    raise QuotaExceeded(
                        f"blocked by Google after {self.rate_limit_hits} consecutive 429s; "
                        "stop and resume later (cache is kept)"
                    ) from exc
                self._sleep(settings.trends_backoff_s * 2**attempt)
            except TrendsError as exc:
                last = exc
                self._pause()
            if self.live_requests >= self.max_requests:
                break
        raise TrendsError(f"Google Trends unavailable for geo={geo}: {last}")
