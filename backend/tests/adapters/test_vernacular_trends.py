from __future__ import annotations

from types import SimpleNamespace

import httpx
import pandas as pd
import pytest

from app.services.sources.google_trends import GoogleTrendsAdapter
from app.services.sources.vernacular import (
    combine_state_interest,
    state_language_code,
    term_languages_by_population,
    vernacular_terms,
)

pytestmark = pytest.mark.adapters


def title(name="Jujutsu Kaisen"):
    return SimpleNamespace(name=name, english_title=None)


def client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def wiki_handler(links):
    def handler(request: httpx.Request) -> httpx.Response:
        if "opensearch" in str(request.url):
            return httpx.Response(200, json=["q", ["Jujutsu Kaisen"], [], []])
        return httpx.Response(200, json={"query": {"pages": {"1": {"langlinks": links}}}})

    return handler


def test_languages_are_ordered_by_state_population_and_mapped():
    order = term_languages_by_population()
    assert order[0] == "hi" and "ta" in order and "bn" in order
    assert state_language_code("Tamil Nadu") == "ta" and state_language_code("Nowhere") is None


def test_vernacular_terms_come_from_wikipedia_langlinks():
    links = [
        {"lang": "ta", "*": "ஜுஜுட்சு கைசென்"},
        {"lang": "fr", "*": "Jujutsu Kaisen"},
        {"lang": "hi", "*": "जुजुत्सु कैसेन"},
    ]
    terms = vernacular_terms(client(wiki_handler(links)), title())
    assert terms == [("hi", "जुजुत्सु कैसेन"), ("ta", "ஜுஜுட்சு கைசென்")]


def test_vernacular_terms_empty_on_poor_match_or_http_error():
    nomatch = lambda r: httpx.Response(200, json=["q", ["Banana"], [], []])  # noqa: E731
    assert vernacular_terms(client(nomatch), title()) == []
    boom = lambda r: httpx.Response(500)  # noqa: E731
    assert vernacular_terms(client(boom), title()) == []


def test_combine_weights_the_local_language_double_and_skips_zero_terms():
    base = {"Kerala": 50.0, "Tamil Nadu": 50.0}
    tamil = {"Kerala": 50.0, "Tamil Nadu": 100.0}
    zeros = {"Kerala": 0.0, "Tamil Nadu": 0.0}
    out = combine_state_interest([("en", base), ("ta", tamil), ("hi", zeros)])
    assert out["Tamil Nadu"] == pytest.approx((50 + 2 * 100) / 3, abs=0.01)
    assert out["Kerala"] == 50.0
    assert combine_state_interest([("en", zeros)]) == {}


class FakeTrends:
    """pytrends stand-in: Tamil Nadu is hot for the Tamil term only."""

    def __init__(self):
        self.term = None

    def build_payload(self, terms, timeframe, geo):
        self.term = terms[0]

    def interest_over_time(self):
        frame = pd.DataFrame({self.term: [40.0] * 91, "One Piece": [80.0] * 91})
        frame["isPartial"] = False
        return frame

    def interest_by_region(self, resolution, inc_low_vol):
        hot = 100.0 if self.term == "தமிழ்" else 40.0
        return pd.DataFrame({self.term: [hot, 40.0]}, index=pd.Index(["Tamil Nadu", "Kerala"]))


def make_adapter(provider, **kwargs):
    GoogleTrendsAdapter._cache.clear()
    GoogleTrendsAdapter._blocked_until = 0.0
    fake = FakeTrends()
    return GoogleTrendsAdapter(
        trends_factory=lambda: fake, term_provider=provider, pause_seconds=0, **kwargs
    )


def test_trends_adds_native_terms_to_the_state_split():
    adapter = make_adapter(lambda t: [("ta", "தமிழ்")])
    evidence = adapter.collect(title())
    assert evidence.status == "available"
    assert evidence.provenance["terms"] == "en:Jujutsu Kaisen | ta:தமிழ்"
    # Tamil term counts double in Tamil Nadu: (40 + 2 * 100) / 3
    assert evidence.regional["Tamil Nadu"]["interest"] == pytest.approx(80.0)
    assert evidence.regional["Kerala"]["interest"] == pytest.approx(40.0)


def test_trends_without_native_terms_is_unchanged():
    evidence = make_adapter(None).collect(title())
    assert evidence.provenance["terms"] == "en:Jujutsu Kaisen"
    assert evidence.regional["Tamil Nadu"]["interest"] == 40.0


def test_trends_survives_a_failing_term_provider():
    def broken(_title):
        raise RuntimeError("wikipedia down")

    evidence = make_adapter(broken).collect(title())
    assert evidence.status == "available" and evidence.regional["Tamil Nadu"]["interest"] == 40.0
