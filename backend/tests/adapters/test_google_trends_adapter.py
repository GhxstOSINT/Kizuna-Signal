from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from app.services.sources.google_trends import GoogleTrendsAdapter

pytestmark = pytest.mark.adapters


def make_title(name="Frieren", english_title=None):
    return SimpleNamespace(name=name, english_title=english_title)


class FakeTrends:
    def __init__(self, columns, error=None, calls=None):
        self.columns = columns
        self.error = error
        self.calls = calls if calls is not None else []

    def build_payload(self, terms, timeframe, geo):
        self.calls.append((list(terms), timeframe, geo))

    def interest_by_region(self, resolution, inc_low_vol):
        if self.error:
            raise self.error
        return pd.DataFrame(
            {"Frieren": [100, 20, 0]}, index=pd.Index(["Nagaland", "Delhi NCR", "Narnia"])
        )

    def interest_over_time(self):
        if self.error:
            raise self.error
        frame = pd.DataFrame(self.columns)
        frame["isPartial"] = False
        frame.iloc[-1, frame.columns.get_loc("isPartial")] = True  # in-progress day is dropped
        return frame


def adapter(fake, **kwargs):
    GoogleTrendsAdapter._cache.clear()
    GoogleTrendsAdapter._blocked_until = 0.0
    return GoogleTrendsAdapter(trends_factory=lambda: fake, **kwargs)


def flat(value, n=91):
    return [value] * n


def test_metrics_compare_title_with_benchmark():
    fake = FakeTrends({"Frieren": flat(25), "One Piece": flat(100)})

    evidence = adapter(fake).collect(make_title())

    assert evidence.status == "available"
    assert evidence.metrics["relative_interest"] == 50.0  # sqrt(0.25) of the benchmark
    assert evidence.metrics["momentum"] == 50.0  # flat series
    assert evidence.metrics["stability"] == 100.0
    assert fake.calls == [
        (["Frieren", "One Piece"], "today 3-m", "IN"),
        (["Frieren"], "today 3-m", "IN"),  # second request: state split, title alone
    ]
    assert evidence.regional == {"Nagaland": {"interest": 100.0}, "Delhi": {"interest": 20.0}}
    assert evidence.provenance["mode"] == "live"
    assert evidence.provenance["benchmark"] == "One Piece"


def test_rising_interest_scores_high_momentum():
    series = flat(10, 77) + flat(40, 14)
    fake = FakeTrends({"Frieren": series, "One Piece": flat(100)})

    evidence = adapter(fake).collect(make_title())

    assert evidence.metrics["momentum"] > 85


def test_title_equal_to_benchmark_skips_the_anchor():
    fake = FakeTrends({"One Piece": flat(80)})

    evidence = adapter(fake).collect(make_title("One Piece"))

    assert fake.calls[0][0] == ["One Piece"]
    assert evidence.provenance["benchmark"] == "none"
    assert evidence.metrics["relative_interest"] == 80.0


def test_no_interest_is_unavailable_not_zero_scored():
    fake = FakeTrends({"Shadow Bloom": flat(0), "One Piece": flat(100)})

    evidence = adapter(fake).collect(make_title("Shadow Bloom"))

    assert evidence.status == "unavailable"
    assert evidence.metrics == {}


def test_rate_limit_triggers_cooldown_without_more_requests():
    calls: list = []
    fake = FakeTrends(
        {},
        error=Exception("The request failed: Google returned a response with code 429"),
        calls=calls,
    )
    now = {"t": 1000.0}
    a = adapter(fake, cooldown_seconds=900, clock=lambda: now["t"])

    first = a.collect(make_title("Frieren"))
    second = a.collect(make_title("Bleach"))

    assert first.status == second.status == "unavailable"
    assert "rate limit" in first.warnings[0].lower()
    assert "retrying in" in second.warnings[0]
    assert len(calls) == 1  # second title never hit Google during the cool-down

    now["t"] += 901
    a.collect(make_title("Naruto"))
    assert len(calls) == 2


def test_repeat_lookup_is_served_from_cache():
    calls: list = []
    fake = FakeTrends({"Frieren": flat(25), "One Piece": flat(100)}, calls=calls)
    a = adapter(fake)

    first = a.collect(make_title())
    second = a.collect(make_title())

    assert first.status == "available"
    assert second.status == "cached"
    assert len(calls) == 2  # national + state requests for the first lookup only


def test_other_errors_degrade_to_unavailable():
    fake = FakeTrends({}, error=ConnectionError("offline"))

    evidence = adapter(fake).collect(make_title())

    assert evidence.status == "unavailable"
    assert "request failed" in evidence.warnings[0]
