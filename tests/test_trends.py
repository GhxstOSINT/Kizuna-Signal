from datetime import date, timedelta

import pandas as pd
import pytest

from app.core.config import settings
from app.adapters.google_trends import QuotaExceeded, RateLimited, TrendsClient, TrendsError
from app.ml.demand import MIN_VALID_STATES, collect_title, is_eligible, search_term, summarize_state
from app.ml.features import build_rows
from app.ml.schema import TitleRecord
from app.ml.states import PILOT_STATES

RELEASE = date(2021, 4, 1)


def title(**over):
    base = dict(title_id="anilist:1", franchise_id="anilist:1", english_title="Demon Slayer Kimetsu",
                original_release_date=RELEASE)
    return TitleRecord(**{**base, **over})


def series(start, end, pre=2, post=30, anchor=50, partial_last=True):
    rows, d = [], start
    while d <= end:
        rows.append({"date": d.isoformat(), "values": {}, "partial": False})
        d += timedelta(weeks=1)
    return rows, pre, post, anchor, partial_last


def fake_fetcher(post_by_geo=None, pre=2, calls=None):
    post_by_geo = post_by_geo or {}

    def fetch(terms, geo, start, end):
        if calls is not None:
            calls.append(geo)
        out, d = [], start
        while d <= end:
            value = pre if d < RELEASE else post_by_geo.get(geo, 30)
            out.append({"date": d.isoformat(), "values": {terms[0]: value, terms[1]: 50}, "partial": False})
            d += timedelta(weeks=1)
        out[-1]["partial"] = True  # Trends marks the latest period as partial
        return out

    return fetch


def client(tmp_path, fetcher, **kw):
    return TrendsClient(fetcher=fetcher, raw_dir=tmp_path, sleep=lambda s: None, **kw)


def test_search_term_adds_anime_for_short_names_and_tracks_variant():
    assert search_term(title(english_title="Monster")) == ("Monster anime", "english")
    assert search_term(title(english_title="Attack on Titan: The Final Season Part 2"))[0] == "Attack on Titan"
    assert search_term(title(english_title=None, romanized_title="Tabi no Hanashi Ookii"))[1] == "romanized"
    assert search_term(title(english_title=None)) is None


def test_second_fetch_comes_from_cache(tmp_path):
    calls = []
    c = client(tmp_path, fake_fetcher(calls=calls))
    a = c.fetch("x anime", "IN-MH", RELEASE - timedelta(weeks=12), RELEASE + timedelta(weeks=52))
    b = c.fetch("x anime", "IN-MH", RELEASE - timedelta(weeks=12), RELEASE + timedelta(weeks=52))
    assert not a["from_cache"] and b["from_cache"] and len(calls) == 1
    assert a["terms"][1] == settings.trends_anchor


def test_rate_limit_backs_off_then_succeeds(tmp_path):
    attempts = {"n": 0}
    good = fake_fetcher()

    def flaky(terms, geo, start, end):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RateLimited("429")
        return good(terms, geo, start, end)

    c = client(tmp_path, flaky)
    assert c.fetch("x anime", "IN-MH", RELEASE - timedelta(weeks=12), RELEASE + timedelta(weeks=52))["rows"]
    assert attempts["n"] == 3


def test_persistent_failure_raises_and_caches_nothing(tmp_path):
    def broken(*a):
        raise TrendsError("boom")

    c = client(tmp_path, broken)
    with pytest.raises(TrendsError, match="unavailable"):
        c.fetch("x anime", "IN-MH", RELEASE - timedelta(weeks=12), RELEASE + timedelta(weeks=52))
    assert not list(tmp_path.rglob("*.json"))


def test_request_budget_is_enforced(tmp_path):
    c = client(tmp_path, fake_fetcher(), max_requests=2)
    s, e = RELEASE - timedelta(weeks=12), RELEASE + timedelta(weeks=52)
    c.fetch("a anime", "IN-MH", s, e)
    c.fetch("a anime", "IN-DL", s, e)
    with pytest.raises(QuotaExceeded):
        c.fetch("a anime", "IN-KA", s, e)


def test_collect_title_labels_sum_to_one_and_demand_is_pre_only(tmp_path):
    post = {g: 10 + 10 * i for i, g in enumerate(PILOT_STATES)}
    c = client(tmp_path, fake_fetcher(post))
    demand, labels, rep = collect_title(c, title(), PILOT_STATES)
    assert rep["error"] is None and rep["states_ok"] == len(PILOT_STATES)
    df = pd.DataFrame(labels)
    assert df["share"].sum() == pytest.approx(1.0)
    # the state with the largest post-release interest has the largest share
    assert df.loc[df["share"].idxmax(), "state"] == PILOT_STATES[-1]
    assert all(k.startswith("pre_") for k in demand[0] if k not in ("title_id", "state"))


def test_pre_features_do_not_depend_on_post_release_data(tmp_path):
    a = collect_title(client(tmp_path / "a", fake_fetcher({g: 10 for g in PILOT_STATES})), title(), PILOT_STATES)[0]
    b = collect_title(client(tmp_path / "b", fake_fetcher({g: 90 for g in PILOT_STATES})), title(), PILOT_STATES)[0]
    assert pd.DataFrame(a).equals(pd.DataFrame(b))


def test_low_signal_states_are_dropped_and_title_dropped_when_too_few(tmp_path):
    post = {g: 0 for g in PILOT_STATES[: len(PILOT_STATES) - MIN_VALID_STATES + 1]}
    c = client(tmp_path, fake_fetcher(post))
    demand, labels, rep = collect_title(c, title(), PILOT_STATES)
    assert labels == [] and rep["error"] == "too_few_states_with_signal"


def test_title_survives_when_enough_states_have_signal(tmp_path):
    post = {g: 0 for g in PILOT_STATES[:2]}
    _, labels, rep = collect_title(client(tmp_path, fake_fetcher(post)), title(), PILOT_STATES)
    assert len(labels) == len(PILOT_STATES) - 2 and rep["error"] is None


def test_partial_period_is_ignored():
    rows = [{"date": (RELEASE + timedelta(weeks=i)).isoformat(),
             "values": {"t": 10, "anime": 50}, "partial": i == 3} for i in range(4)]
    s = summarize_state(rows, "t", "anime", RELEASE)
    assert s["post_ratio"] == pytest.approx(30 / 150)


def test_eligibility_requires_full_post_release_window():
    assert is_eligible(title(), date(2023, 1, 1))
    assert not is_eligible(title(original_release_date=date(2022, 12, 1)), date(2023, 1, 1))
    assert not is_eligible(title(original_release_date=None), date(2023, 1, 1))


def test_build_rows_rejects_non_pre_demand_columns():
    content = pd.DataFrame({"title_id": ["a"], "genre_X": [1]})
    labels = pd.DataFrame({"title_id": ["a"], "state": ["IN-MH"], "share": [1.0]})
    ok = pd.DataFrame({"title_id": ["a"], "state": ["IN-MH"], "pre_level": [0.1]})
    assert "pre_level" in build_rows(content, labels, ["IN-MH"], demand=ok).columns
    with pytest.raises(ValueError, match="pre-release"):
        build_rows(content, labels, ["IN-MH"], demand=ok.assign(post_ratio=0.5))
