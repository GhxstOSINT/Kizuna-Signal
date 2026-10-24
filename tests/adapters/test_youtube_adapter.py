from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest

from app.services.sources.youtube import YouTubeAdapter

pytestmark = pytest.mark.adapters

NOW = datetime(2026, 10, 24, tzinfo=UTC)
KEY = "test-key-123"


def make_title(name="Frieren", english_title=None):
    return SimpleNamespace(name=name, english_title=english_title)


def video(video_id, title, views, likes, comments, published="2025-10-24T00:00:00Z"):
    return {
        "id": video_id,
        "snippet": {"title": title, "publishedAt": published},
        "statistics": {
            "viewCount": str(views),
            "likeCount": str(likes),
            "commentCount": str(comments),
        },
    }


def adapter_for(handler, ttl=3600, clock=lambda: 0.0):
    YouTubeAdapter._cache.clear()
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return YouTubeAdapter(client, KEY, cache_ttl_seconds=ttl, now=lambda: NOW, clock=clock)


def standard_handler(videos, calls=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request.url.path)
        assert request.headers["x-goog-api-key"] == KEY
        assert "key=" not in str(request.url)  # key must never be in the URL (logged by httpx)
        if request.url.path.endswith("/search"):
            return httpx.Response(
                200, json={"items": [{"id": {"videoId": v["id"]}} for v in videos]}
            )
        return httpx.Response(200, json={"items": videos})

    return handler


def test_metrics_from_search_and_video_stats():
    videos = [
        video("a", "Frieren Official Trailer", 1_000_000, 40_000, 5_000),
        video("b", "Frieren: Beyond Journey's End | Trailer 2", 3_000_000, 90_000, 10_000),
        video("c", "Unrelated cooking video", 9_000_000, 1, 1),
    ]
    evidence = adapter_for(standard_handler(videos)).collect(make_title())

    assert evidence.status == "available"
    assert evidence.metrics["matched_videos"] == 2.0  # unrelated video is filtered out
    assert evidence.metrics["total_views"] == 4_000_000.0
    assert evidence.metrics["attention"] == pytest.approx(82.5, abs=0.1)  # log10(4M)/8
    assert evidence.metrics["engagement_quality"] == pytest.approx(60.4, abs=0.1)  # 3.6% / 6%
    assert evidence.metrics["velocity"] == pytest.approx(80.8, abs=0.2)  # ~11k views/day
    assert evidence.provenance["mode"] == "live"
    assert KEY not in str(evidence.provenance) + str(evidence.warnings)


def test_no_matching_videos_is_unavailable():
    videos = [video("c", "Unrelated cooking video", 9_000_000, 1, 1)]

    evidence = adapter_for(standard_handler(videos)).collect(make_title())

    assert evidence.status == "unavailable"
    assert evidence.metrics == {}


def test_quota_exceeded_degrades_without_leaking_key():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": {"errors": [{"reason": "quotaExceeded"}]}})

    evidence = adapter_for(handler).collect(make_title())

    assert evidence.status == "unavailable"
    assert "quotaExceeded" in evidence.warnings[0]
    assert KEY not in evidence.warnings[0]


def test_network_failure_degrades_to_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    assert adapter_for(handler).collect(make_title()).status == "unavailable"


def test_repeat_lookup_uses_cache_and_skips_quota():
    calls: list[str] = []
    videos = [video("a", "Frieren Official Trailer", 1_000_000, 40_000, 5_000)]
    adapter = adapter_for(standard_handler(videos, calls))

    first = adapter.collect(make_title())
    second = adapter.collect(make_title())

    assert first.status == "available"
    assert second.status == "cached"
    assert second.metrics == first.metrics
    assert len(calls) == 2  # one search + one videos.list, none for the second analysis


def test_cache_expires():
    now = {"t": 0.0}
    calls: list[str] = []
    videos = [video("a", "Frieren Official Trailer", 1_000_000, 40_000, 5_000)]
    adapter = adapter_for(standard_handler(videos, calls), ttl=100, clock=lambda: now["t"])

    adapter.collect(make_title())
    now["t"] = 101.0
    assert adapter.collect(make_title()).status == "available"
    assert len(calls) == 4
