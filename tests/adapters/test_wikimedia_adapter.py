from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import httpx
import pytest

from app.services.sources.wikimedia import WikimediaAdapter, match_score

pytestmark = pytest.mark.adapters

TODAY = date(2026, 10, 24)


def make_title(name="Demon Slayer", english_title=None):
    return SimpleNamespace(name=name, english_title=english_title)


def pageview_items(article, per_day, days=90):
    from datetime import timedelta

    end = TODAY - timedelta(days=1)
    return {
        "items": [
            {
                "article": article,
                "timestamp": (end - timedelta(days=days - 1 - i)).strftime("%Y%m%d") + "00",
                "views": per_day,
            }
            for i in range(days)
        ]
    }


def adapter_for(handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return WikimediaAdapter(client, lookback_days=90, today=lambda: TODAY)


def test_live_metrics_from_search_and_pageviews():
    def handler(request: httpx.Request) -> httpx.Response:
        if "rest.php/v1/search/title" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "pages": [
                        {
                            "key": "Demon_Slayer",
                            "title": "Demon Slayer",
                            "description": "Topics referred to by the same term",
                        },
                        {
                            "key": "Demon_Slayer:_Kimetsu_no_Yaiba",
                            "title": "Demon Slayer: Kimetsu no Yaiba",
                            "description": "Japanese manga series",
                        },
                    ]
                },
            )
        assert "Demon_Slayer%3A_Kimetsu_no_Yaiba" in str(request.url)
        return httpx.Response(200, json=pageview_items("Demon_Slayer", 1000))

    evidence = adapter_for(handler).collect(make_title())

    assert evidence.status == "available"
    assert evidence.metrics["avg_daily_views_30d"] == 1000.0
    assert evidence.metrics["curiosity"] == pytest.approx(75.0, abs=0.1)  # log10(1001)/4
    assert evidence.metrics["sustained_interest"] == 100.0
    assert evidence.provenance["mode"] == "live"
    assert evidence.provenance["articles"] == "en:Demon_Slayer:_Kimetsu_no_Yaiba"
    assert evidence.provenance["window"] == "2026-07-26..2026-10-23"


def test_no_confident_match_is_unavailable_not_fabricated():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"pages": [{"key": "Banana", "title": "Banana"}]})

    evidence = adapter_for(handler).collect(make_title("Shadow Bloom"))

    assert evidence.status == "unavailable"
    assert evidence.metrics == {}
    assert "No confident Wikipedia article match" in evidence.warnings[0]


def test_http_failure_degrades_to_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    evidence = adapter_for(handler).collect(make_title())

    assert evidence.status == "unavailable"
    assert "Wikimedia request failed" in evidence.warnings[0]


def test_server_error_degrades_to_unavailable():
    evidence = adapter_for(lambda request: httpx.Response(503)).collect(make_title())

    assert evidence.status == "unavailable"


def test_japanese_title_also_queries_ja_wikipedia():
    hosts = []

    def handler(request: httpx.Request) -> httpx.Response:
        if "rest.php/v1/search/title" in str(request.url):
            hosts.append(request.url.host)
            if request.url.host != "ja.wikipedia.org":
                return httpx.Response(200, json={"pages": []})
            return httpx.Response(
                200,
                json={"pages": [{"key": "鬼滅の刃", "title": "鬼滅の刃", "description": "漫画"}]},
            )
        return httpx.Response(200, json=pageview_items("x", 500))

    evidence = adapter_for(handler).collect(make_title("鬼滅の刃", "Demon Slayer"))

    assert "ja.wikipedia.org" in hosts
    assert evidence.status == "available"
    assert evidence.metrics["avg_daily_views_30d"] == 500.0  # ja article only; en had no match


def test_match_score_prefers_exact_and_prefix_matches():
    assert match_score("Demon Slayer", "Demon Slayer") == 1.0
    assert match_score("Demon Slayer", "Demon Slayer: Kimetsu no Yaiba") >= 0.9
    assert match_score("Shadow Bloom", "Banana") < 0.6


def test_near_miss_article_is_rejected():
    assert match_score("Shadow Bloom", "Shadow Brook") < 0.85
