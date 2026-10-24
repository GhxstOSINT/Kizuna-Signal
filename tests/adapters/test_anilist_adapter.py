from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from app.services.sources.anilist import AniListAdapter, anilist_genres, popularity_signal

pytestmark = pytest.mark.adapters


def make_title(name="Frieren", genres=("fantasy", "adventure"), themes=("magic",)):
    return SimpleNamespace(
        name=name,
        english_title=name,
        primary_genre=genres[0],
        genres=list(genres),
        themes=list(themes),
    )


def media(id_, romaji, popularity, genres, tags=(), english=None, score=80):
    return {
        "id": id_,
        "title": {"romaji": romaji, "english": english, "native": None},
        "popularity": popularity,
        "favourites": 10,
        "averageScore": score,
        "genres": list(genres),
        "tags": [{"name": t, "rank": 80} for t in tags],
        "format": "TV",
        "status": "FINISHED",
        "seasonYear": 2023,
        "description": "d",
    }


def adapter_for(lookup, pool, **kwargs):
    AniListAdapter._cache.clear()
    AniListAdapter._blocked_until = 0.0

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        if "search:" in body or "$search" in body:
            return httpx.Response(200, json={"data": {"Page": {"media": lookup}}})
        return httpx.Response(200, json={"data": {"Page": {"media": pool}}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return AniListAdapter(client, **kwargs)


POOL = [
    media(1, "Magic Quest", 400_000, ["Fantasy", "Adventure"], ["Magic"]),
    media(2, "Magic Quest Season 2", 300_000, ["Fantasy", "Adventure"], ["Magic"]),
    media(3, "Dragon Road", 200_000, ["Fantasy", "Adventure"]),
    media(4, "Elf Tale", 150_000, ["Fantasy"], ["Magic"]),
    media(5, "Sword Saga", 120_000, ["Fantasy", "Adventure"]),
    media(6, "Frieren", 500_000, ["Fantasy", "Adventure"], ["Magic"]),  # the title itself
]


def test_listed_title_gets_community_metrics_and_comparables():
    lookup = [media(6, "Sousou no Frieren", 500_000, ["Fantasy"], ["Magic"], english="Frieren")]

    evidence = adapter_for(lookup, POOL).collect(make_title())

    assert evidence.status == "available"
    assert evidence.metrics["community_strength"] == pytest.approx(
        0.6 * popularity_signal(500_000) + 0.4 * 80, abs=0.01
    )
    assert evidence.metrics["metadata_completeness"] == 100.0
    names = [c["title"] for c in evidence.comparables]
    assert "Frieren" not in names  # never a comparable to itself
    assert "Magic Quest Season 2" not in names  # sequels collapse into the franchise
    assert {"Magic Quest", "Dragon Road"} <= set(names)
    assert all(
        0 <= c["similarity"] <= 1 and 0 <= c["market_signal"] <= 100 for c in evidence.comparables
    )


def test_unlisted_title_still_yields_genre_comparables():
    evidence = adapter_for([], POOL[:5]).collect(make_title("Shadow Bloom"))

    assert evidence.status == "available"
    assert "community_strength" not in evidence.metrics
    assert any("not listed on AniList" in w for w in evidence.warnings)
    assert evidence.comparables


def test_comparable_signal_is_discounted_for_top_of_genre_pool():
    evidence = adapter_for([], POOL[:5]).collect(make_title("Shadow Bloom"))
    top = next(c for c in evidence.comparables if c["title"] == "Magic Quest")

    assert top["market_signal"] == pytest.approx(0.85 * popularity_signal(400_000), abs=0.01)


def test_rate_limit_triggers_cooldown():
    AniListAdapter._cache.clear()
    AniListAdapter._blocked_until = 0.0
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(429, headers={"Retry-After": "60"})

    now = {"t": 100.0}
    adapter = AniListAdapter(
        httpx.Client(transport=httpx.MockTransport(handler)), clock=lambda: now["t"]
    )

    first = adapter.collect(make_title("A"))
    second = adapter.collect(make_title("B"))

    assert first.status == second.status == "unavailable"
    assert len(calls) == 1
    AniListAdapter._blocked_until = 0.0


def test_repeat_lookup_is_cached():
    adapter = adapter_for([], POOL[:5])

    assert adapter.collect(make_title("Shadow Bloom")).status == "available"
    assert adapter.collect(make_title("Shadow Bloom")).status == "cached"


def test_genre_mapping_ignores_unknown_and_adult_genres():
    title = make_title(genres=("Fantasy", "sci fi", "hentai", "made up"))

    assert anilist_genres(title) == ["Fantasy", "Sci-Fi"]


def test_popularity_signal_is_log_scaled_and_bounded():
    assert popularity_signal(0) == 0
    assert popularity_signal(1_000) == 0
    assert popularity_signal(1_000_000) == 100
    assert popularity_signal(10_000_000) == 100
    assert 0 < popularity_signal(30_000) < popularity_signal(300_000) < 100
