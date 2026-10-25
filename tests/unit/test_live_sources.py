import tempfile

import httpx
import pytest

from app.core.config import Settings
from app.db.models import Title
from app.services.sources import live
from app.services.sources.live import (
    AniListLive,
    LiveSourceRegistry,
    RegionalContextCensus,
    WikimediaLive,
    YouTubeLive,
    best_match,
)


def make_title(**kw) -> Title:
    base = dict(name="Jujutsu Kaisen", english_title=None, synopsis="x" * 50, content_format="Anime series",
                primary_genre="Action", genres=["Action"], themes=[], source_material="Manga",
                expected_release_period="2027", target_platform="OTT", target_languages=["Hindi", "Tamil"],
                target_states=[], marketing_budget="medium", trailer_url=None)
    base.update(kw)
    return Title(**base)


def client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def _clear_cache():
    live._cache.clear()


def test_best_match_rejects_unrelated_articles():
    title = make_title(name="Shadow Bloom")
    assert best_match(title, ["Banana", "Football"]) is None
    assert best_match(title, ["Shadow Bloom (anime)", "x"])[0] == "Shadow Bloom (anime)"


def test_wikimedia_scores_pageviews_and_logs_match():
    def handler(request: httpx.Request) -> httpx.Response:
        if "opensearch" in str(request.url):
            return httpx.Response(200, json=["q", ["Jujutsu Kaisen"], [], []])
        items = [{"views": 4000 + (i % 5) * 100} for i in range(90)]
        return httpx.Response(200, json={"items": items})

    ev = WikimediaLive(client(handler), Settings()).collect(make_title())
    assert ev.status == "available" and 0 < ev.metrics["curiosity"] <= 100
    assert ev.provenance["article"] == "Jujutsu_Kaisen" and ev.provenance["mode"] == "live"
    assert WikimediaLive(client(handler), Settings()).collect(make_title()).status == "cached"


def test_wikimedia_unavailable_when_no_article_or_http_error():
    none = lambda r: httpx.Response(200, json=["q", [], [], []])  # noqa: E731
    assert WikimediaLive(client(none), Settings()).collect(make_title()).status == "unavailable"
    boom = lambda r: httpx.Response(500)  # noqa: E731
    assert WikimediaLive(client(boom), Settings()).collect(make_title(name="Other")).status == "unavailable"


def test_anilist_matches_and_scores():
    payload = {"data": {"Page": {"media": [{
        "id": 1, "title": {"romaji": "Jujutsu Kaisen", "english": "Jujutsu Kaisen"}, "format": "TV",
        "genres": ["Action"], "tags": [{"name": "School"}], "description": "d",
        "studios": {"nodes": [{"name": "MAPPA"}]}, "startDate": {"year": 2020},
        "averageScore": 84, "popularity": 987994, "favourites": 1}]}}}
    ev = AniListLive(client(lambda r: httpx.Response(200, json=payload)), Settings()).collect(make_title())
    assert ev.status == "available" and ev.metrics["metadata_completeness"] == 100.0
    assert 80 <= ev.metrics["historical_affinity"] <= 100


def test_anilist_rejects_poor_match():
    payload = {"data": {"Page": {"media": [{"id": 2, "title": {"romaji": "Totally Different", "english": None},
        "genres": [], "tags": [], "description": None, "studios": {"nodes": []},
        "startDate": {"year": None}, "averageScore": None, "popularity": 1, "favourites": 0, "format": "TV"}]}}}
    ev = AniListLive(client(lambda r: httpx.Response(200, json=payload)), Settings()).collect(make_title())
    assert ev.status == "unavailable"


def test_youtube_needs_key_and_scores_statistics():
    assert YouTubeLive(client(lambda r: httpx.Response(200)), Settings(youtube_api_key=None)).collect(make_title()).status == "unavailable"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": [{
            "statistics": {"viewCount": "5000000", "likeCount": "200000", "commentCount": "9000"},
            "snippet": {"publishedAt": "2026-01-01T00:00:00Z"}}]})

    title = make_title(trailer_url="https://www.youtube.com/watch?v=abcdef12345")
    unrelated = lambda r: httpx.Response(200, json={"items": [{"id": {"videoId": "zzz"}, "snippet": {"title": "Cat video"}}]})  # noqa: E731
    assert YouTubeLive(client(unrelated), Settings(youtube_api_key="test")).collect(make_title()).status == "unavailable"
    ev = YouTubeLive(client(handler), Settings(youtube_api_key="test")).collect(title)
    assert ev.status == "available" and ev.metrics["attention"] > 70


def test_regional_context_uses_census_coverage():
    only_hindi = RegionalContextCensus().collect(make_title(target_languages=["Hindi"]))
    broad = RegionalContextCensus().collect(make_title(target_languages=["Hindi", "Tamil", "Telugu"]))
    assert broad.metrics["language_fit"] > only_hindi.metrics["language_fit"] > 0
    assert RegionalContextCensus().collect(make_title(target_languages=[])).metrics["language_fit"] == 0


def test_registry_never_raises_and_respects_disabled():
    reg = LiveSourceRegistry(Settings(), client(lambda r: httpx.Response(500)))
    results = reg.collect(make_title(), {"wikimedia"})
    assert [r.source for r in results] == list(reg.SOURCE_NAMES)
    assert next(r for r in results if r.source == "wikimedia").status == "unavailable"
    assert next(r for r in results if r.source == "regional_context").status == "available"


def test_disk_cache_makes_reruns_stable():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if "opensearch" in str(request.url):
            return httpx.Response(200, json=["q", ["Jujutsu Kaisen"], [], []])
        return httpx.Response(200, json={"items": [{"views": 3000} for _ in range(90)]})

    with tempfile.TemporaryDirectory() as directory:
        settings = Settings(source_cache_dir=directory)
        first = LiveSourceRegistry(settings, client(handler)).collect(make_title())
        live._cache.clear()
        n = sum('wiki' in c for c in calls)
        second = LiveSourceRegistry(settings, client(handler)).collect(make_title())
    wiki = lambda rs: next(r for r in rs if r.source == "wikimedia")  # noqa: E731
    assert wiki(first).status == "available" and wiki(second).status == "cached"
    assert wiki(first).metrics == wiki(second).metrics and sum('wiki' in c for c in calls) == n
