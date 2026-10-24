"""Every live adapter must turn a misbehaving provider into an unavailable source.

A timeout, a non-JSON body, JSON of the wrong shape or a missing field must never raise, never
produce metrics, and never echo internal exception text into the warnings the API returns.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

import httpx
import pandas as pd
import pytest

from app.services.sources.anilist import AniListAdapter
from app.services.sources.google_trends import GoogleTrendsAdapter
from app.services.sources.wikimedia import WikimediaAdapter
from app.services.sources.youtube import YouTubeAdapter

pytestmark = pytest.mark.adapters

TODAY = date(2026, 10, 24)
TITLE = SimpleNamespace(
    name="Frieren",
    english_title="Frieren",
    primary_genre="fantasy",
    genres=["fantasy", "adventure"],
    themes=["magic"],
)
INTERNALS = ("no attribute", "KeyError", "TypeError", "NoneType", "not subscriptable", "Traceback")


def wikimedia(handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return WikimediaAdapter(client, lookback_days=90, today=lambda: TODAY)


def youtube(handler):
    YouTubeAdapter._cache.clear()
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return YouTubeAdapter(client, "key", now=lambda: datetime(2026, 10, 24, tzinfo=UTC))


def anilist(handler):
    AniListAdapter._cache.clear()
    AniListAdapter._blocked_until = 0.0
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return AniListAdapter(client)


ADAPTERS = {"wikimedia": wikimedia, "youtube": youtube, "anilist": anilist}


def timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("timed out", request=request)


def respond(**kwargs):
    return lambda request: httpx.Response(200, **kwargs)


# Each bad response is served for every request the adapter makes.
BAD_RESPONSES = {
    "timeout": timeout,
    "connect_timeout": lambda request: (_ for _ in ()).throw(httpx.ConnectTimeout("no route")),
    "html_instead_of_json": respond(content=b"<html>502 Bad Gateway</html>"),
    "empty_body": respond(content=b""),
    "json_null": respond(content=b"null"),
    "json_list": respond(json=[]),
    "json_string": respond(json="oops"),
    "empty_object": respond(json={}),
    "wrong_item_types": respond(
        json={"pages": "oops", "items": "oops", "data": {"Page": {"media": "oops"}}}
    ),
    "items_are_numbers": respond(
        json={"pages": [1], "items": [1], "data": {"Page": {"media": [1]}}}
    ),
    "media_missing_fields": respond(json={"data": {"Page": {"media": [{"id": 1}]}}}),
}


@pytest.mark.parametrize("failure", BAD_RESPONSES)
@pytest.mark.parametrize("adapter_name", ADAPTERS)
def test_bad_provider_response_degrades_to_unavailable(adapter_name, failure):
    evidence = ADAPTERS[adapter_name](BAD_RESPONSES[failure]).collect(TITLE)

    assert evidence.status == "unavailable"
    assert evidence.metrics == {}
    assert evidence.comparables == []
    assert evidence.warnings
    text = " ".join(evidence.warnings)
    assert not any(marker in text for marker in INTERNALS), text


def test_wikimedia_pageviews_missing_fields_is_a_clean_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        if "rest.php/v1/search/title" in str(request.url):
            return httpx.Response(200, json={"pages": [{"key": "Frieren", "title": "Frieren"}]})
        return httpx.Response(200, json={"items": [{"views": 5}]})  # no "timestamp"

    evidence = wikimedia(handler).collect(TITLE)

    assert evidence.status == "unavailable"
    assert "unexpected format" in evidence.warnings[0]


def test_youtube_video_missing_snippet_is_a_clean_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json={"items": [{"id": {"videoId": "a"}}]})
        return httpx.Response(200, json={"items": [{"id": "a", "statistics": {}}]})

    evidence = youtube(handler).collect(TITLE)

    assert evidence.status == "unavailable"
    assert "unexpected format" in evidence.warnings[0]


class BrokenTrends:
    def __init__(self, frame=None, error=None):
        self.frame = frame
        self.error = error

    def build_payload(self, *args, **kwargs):
        pass

    def interest_over_time(self):
        if self.error:
            raise self.error
        return self.frame

    def interest_by_region(self, *args, **kwargs):
        return None


TRENDS_FAILURES = {
    "timeout": BrokenTrends(error=TimeoutError("read timed out")),
    "no_frame": BrokenTrends(frame=None),
    "string_instead_of_frame": BrokenTrends(frame="garbage"),
    "missing_keyword_column": BrokenTrends(frame=pd.DataFrame({"other": [1] * 91})),
    "too_short": BrokenTrends(frame=pd.DataFrame({"Frieren": [1] * 5})),
}


@pytest.mark.parametrize("failure", TRENDS_FAILURES)
def test_google_trends_bad_response_degrades_to_unavailable(failure):
    GoogleTrendsAdapter._cache.clear()
    GoogleTrendsAdapter._blocked_until = 0.0
    adapter = GoogleTrendsAdapter(trends_factory=lambda: TRENDS_FAILURES[failure])

    evidence = adapter.collect(TITLE)

    assert evidence.status == "unavailable"
    assert evidence.metrics == {}
    text = " ".join(evidence.warnings)
    assert not any(marker in text for marker in INTERNALS), text
