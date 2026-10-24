import httpx
import pytest

from app.adapters.anilist import AniListClient, AniListError, records_from_envelope
from app.ml.dataset import assert_no_leakage, clean, split

SYNOPSIS = "<b>A</b> young swordsman&#039;s journey<br>across a ruined kingdom to find his sister."


def media(id_=1, **over):
    base = {
        "id": id_,
        "title": {"romaji": "Tabi", "english": "Journey", "native": "旅"},
        "description": SYNOPSIS,
        "genres": ["Adventure", "Action"],
        "tags": [{"name": "Swordplay"}],
        "studios": {"nodes": [{"name": "Studio X"}]},
        "format": "TV",
        "season": "FALL",
        "seasonYear": 2020,
        "startDate": {"year": 2020, "month": 10, "day": 1},
        "status": "FINISHED",
        "relations": {"edges": [{"relationType": "PREQUEL", "node": {"id": 9, "type": "ANIME"}}]},
        "popularity": 5000,
        "favourites": 300,
        "averageScore": 80,
    }
    return {**base, **over}


def page(items, has_next=False):
    return {"data": {"Page": {"pageInfo": {"currentPage": 1, "hasNextPage": has_next}, "media": items}}}


def client(handler, tmp_path, retries=2):
    return AniListClient(
        raw_dir=tmp_path,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=retries,
        sleep=lambda s: None,
    )


def test_fetch_stores_raw_then_serves_cache(tmp_path):
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(200, json=page([media()]))

    c = client(handler, tmp_path)
    first = c.fetch_page(1)
    second = c.fetch_page(1)
    assert not first["from_cache"] and second["from_cache"]
    assert len(calls) == 1
    assert len(list(tmp_path.rglob("*.json"))) == 1


def test_retries_on_429_and_5xx_then_succeeds(tmp_path):
    responses = iter([httpx.Response(429, headers={"Retry-After": "1"}), httpx.Response(503),
                      httpx.Response(200, json=page([media()]))])
    c = client(lambda req: next(responses), tmp_path, retries=3)
    assert c.fetch_page(1)["response"]["data"]["Page"]["media"][0]["id"] == 1


def test_gives_up_after_bounded_retries(tmp_path):
    c = client(lambda req: httpx.Response(503), tmp_path, retries=2)
    with pytest.raises(AniListError, match="3 attempts"):
        c.fetch_page(1)
    assert not list(tmp_path.rglob("*.json"))


def test_graphql_error_is_not_cached(tmp_path):
    c = client(lambda req: httpx.Response(200, json={"errors": [{"message": "bad"}]}), tmp_path)
    with pytest.raises(AniListError, match="graphql"):
        c.fetch_page(1)


def test_normalize_separates_features_from_outcome(tmp_path):
    c = client(lambda req: httpx.Response(200, json=page([media()])), tmp_path)
    rec = records_from_envelope(c.fetch_page(1))[0]
    assert rec["features"]["synopsis"] == "A young swordsman's journey across a ruined kingdom to find his sister."
    assert rec["features"]["has_prequel"] is True
    assert rec["outcome"]["popularity"] == 5000
    assert "popularity" not in rec["features"]
    assert rec["provenance"]["raw_checksum"]


def test_clean_drops_bad_rows_and_dedupes(tmp_path):
    items = [
        media(1),
        media(1),  # duplicate id
        media(2, status="NOT_YET_RELEASED"),
        media(3, description="short"),
        media(4, genres=[]),
        media(5, popularity=0),
        media(6, format="MUSIC"),
    ]
    c = client(lambda req: httpx.Response(200, json=page(items)), tmp_path)
    kept, dropped = clean(records_from_envelope(c.fetch_page(1)))
    assert [r["anilist_id"] for r in kept] == [1]
    assert dropped == {"duplicate": 1, "not_finished": 1, "short_or_missing_synopsis": 1,
                       "no_genres": 1, "no_popularity_label": 1, "unsupported_format": 1}


def test_split_has_no_leakage(tmp_path):
    c = client(lambda req: httpx.Response(200, json=page([media()])), tmp_path)
    features, labels = split(records_from_envelope(c.fetch_page(1)))
    assert_no_leakage(features)
    assert labels[0]["popularity"] == 5000 and labels[0]["log_popularity"] > 0
    with pytest.raises(ValueError):
        assert_no_leakage([{**features[0], "popularity": 1}])
