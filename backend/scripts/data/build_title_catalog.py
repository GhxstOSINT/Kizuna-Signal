"""Build the super training dataset: top Japanese titles with Japanese / romaji / English names.

Sources (live, public, free):
  - AniList GraphQL: top 500 by popularity each for anime series, anime movies and manga
    (Japan-origin, non-adult). Gives native (Japanese), romaji and English titles plus genres,
    tags, format, year, popularity, score and relations.
  - Wikidata SPARQL: top 500 Japanese live-action TV series and top 500 Japanese films by
    Wikipedia sitelink count, with Japanese and English labels.

Output: data/training/super_training_dataset.csv (one row per title) with a 75/25
train/test `split` assigned by franchise group so sequels, spin-offs and manga-anime
adaptations never straddle the split. Raw API responses are cached in data/training/raw/.

Run from the repository root:  .venv/bin/python backend/scripts/data/build_title_catalog.py
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import httpx
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

ROOT = Path(__file__).resolve().parents[3]  # repository root
OUT_DIR = ROOT / "data/training"
RAW_DIR = OUT_DIR / "raw"
DATASET = OUT_DIR / "super_training_dataset.csv"
STATE_TABLE = ROOT / "data/training/training_table_title_x_state.csv"

PER_CATEGORY = 500
ANILIST_URL = "https://graphql.anilist.co"
WIKIDATA_URL = "https://query.wikidata.org/sparql"
USER_AGENT = "KizunaSignal/0.1 (hackathon research; github hexbyte-work)"
PAGE_SIZE = 50
PAUSE_SECONDS = 2.5  # AniList is degraded to 30 requests/minute
TEST_FRACTION_FOLDS = 4  # 1 of 4 folds -> 25% held out
SEED = 7
MIN_TAG_RANK = 50  # keep tags AniList voters rate as at least 50% relevant
LINK_TYPES = {
    "SEQUEL",
    "PREQUEL",
    "SIDE_STORY",
    "PARENT",
    "SPIN_OFF",
    "ADAPTATION",
    "ALTERNATIVE",
    "SUMMARY",
    "SOURCE",
    "COMPILATION",
    "CONTAINS",
}

ANILIST_CATEGORIES = {
    "anime_series": ("ANIME", "format_in: [TV, TV_SHORT, ONA]"),
    "anime_movie": ("ANIME", "format: MOVIE"),
    "manga": ("MANGA", "format_in: [MANGA, ONE_SHOT]"),
}

QUERY = """
query ($page: Int) {
  Page(page: $page, perPage: %(size)d) {
    pageInfo { hasNextPage }
    media(type: %(type)s, %(fmt)s, countryOfOrigin: JP, isAdult: false, sort: POPULARITY_DESC) {
      id
      title { romaji english native }
      format
      status
      startDate { year }
      episodes
      chapters
      volumes
      duration
      source
      genres
      tags { name rank }
      popularity
      favourites
      averageScore
      studios(isMain: true) { nodes { name } }
      relations { edges { relationType node { id } } }
    }
  }
}
"""


def anilist_pages(client: httpx.Client, media_type: str, fmt: str) -> list[dict]:
    items: list[dict] = []
    query = QUERY % {"size": PAGE_SIZE, "type": media_type, "fmt": fmt}
    page = 1
    while len(items) < PER_CATEGORY:
        for _attempt in range(5):
            response = client.post(ANILIST_URL, json={"query": query, "variables": {"page": page}})
            if response.status_code == 429:
                time.sleep(int(response.headers.get("Retry-After", "30")) + 1)
                continue
            response.raise_for_status()
            break
        else:
            raise RuntimeError("AniList kept rate-limiting; try again in a few minutes")
        payload = response.json()["data"]["Page"]
        items.extend(payload["media"])
        if not payload["pageInfo"]["hasNextPage"]:
            break
        page += 1
        time.sleep(PAUSE_SECONDS)
    return items[:PER_CATEGORY]


def fetch_anilist() -> dict[str, list[dict]]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    result: dict[str, list[dict]] = {}
    with httpx.Client(http2=True, timeout=60, headers={"User-Agent": USER_AGENT}) as client:
        for category, (media_type, fmt) in ANILIST_CATEGORIES.items():
            cache = RAW_DIR / f"anilist_{category}.json"
            if cache.exists():
                result[category] = json.loads(cache.read_text())
                continue
            result[category] = anilist_pages(client, media_type, fmt)
            cache.write_text(json.dumps(result[category], ensure_ascii=False))
            print(f"AniList {category}: {len(result[category])} titles")
    return result


def sparql(client: httpx.Client, query: str) -> list[dict]:
    for attempt in range(4):
        response = client.get(
            WIKIDATA_URL,
            params={"query": query},
            headers={"Accept": "application/sparql-results+json"},
        )
        if response.status_code in (429, 500, 502, 503, 504):
            time.sleep(10 * (attempt + 1))
            continue
        response.raise_for_status()
        return response.json()["results"]["bindings"]
    raise RuntimeError("Wikidata unavailable")


WIKIDATA_CLASSES = {
    # television series / film made only in Japan, only in Japanese (no co-productions), excluding anime
    "jp_tv_series": "Q5398426",
    "jp_film": "Q11424",
}


def fetch_wikidata() -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    with httpx.Client(http2=True, timeout=120, headers={"User-Agent": USER_AGENT}) as client:
        for category, klass in WIKIDATA_CLASSES.items():
            cache = RAW_DIR / f"wikidata_{category}.json"
            if cache.exists():
                result[category] = json.loads(cache.read_text())
                continue
            top = sparql(
                client,
                f"""SELECT ?item ?ja ?en ?sl WHERE {{
                  ?item wdt:P31 wd:{klass}; wdt:P495 wd:Q17; wdt:P364 wd:Q5287; wikibase:sitelinks ?sl .
                  MINUS {{ ?item wdt:P495 ?other FILTER(?other != wd:Q17) }}
                  MINUS {{ ?item wdt:P364 ?lang FILTER(?lang != wd:Q5287) }}
                  MINUS {{ ?item wdt:P136 wd:Q1107 }}
                  MINUS {{ ?item wdt:P136 wd:Q20650540 }}
                  ?item rdfs:label ?ja FILTER(LANG(?ja) = "ja")
                  ?item rdfs:label ?en FILTER(LANG(?en) = "en")
                }} ORDER BY DESC(?sl) LIMIT {PER_CATEGORY + 250}""",
            )
            ids = [row["item"]["value"].rsplit("/", 1)[1] for row in top]
            details: dict[str, dict] = {}
            for start in range(0, len(ids), 150):
                values = " ".join(f"wd:{i}" for i in ids[start : start + 150])
                rows = sparql(
                    client,
                    f"""SELECT ?item (MIN(YEAR(?d)) AS ?year) (GROUP_CONCAT(DISTINCT ?g; separator="|") AS ?genres)
                    WHERE {{ VALUES ?item {{ {values} }}
                      OPTIONAL {{ ?item wdt:P577|wdt:P580 ?d }}
                      OPTIONAL {{ ?item wdt:P136 ?gi . ?gi rdfs:label ?g FILTER(LANG(?g) = "en") }}
                    }} GROUP BY ?item""",
                )
                for row in rows:
                    details[row["item"]["value"].rsplit("/", 1)[1]] = {
                        "year": row.get("year", {}).get("value"),
                        "genres": row.get("genres", {}).get("value", ""),
                    }
                time.sleep(1)
            result[category] = [
                {
                    "id": item_id,
                    "ja": row["ja"]["value"],
                    "en": row["en"]["value"],
                    "sitelinks": int(row["sl"]["value"]),
                    **details.get(item_id, {}),
                }
                for item_id, row in zip(ids, top, strict=True)
            ]
            cache.write_text(json.dumps(result[category], ensure_ascii=False))
            print(f"Wikidata {category}: {len(result[category])} candidates")
    return result


def norm_name(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", (text or "").casefold())


def anilist_rows(data: dict[str, list[dict]]) -> list[dict]:
    rows = []
    for category, items in data.items():
        for rank, item in enumerate(items, start=1):
            title = item["title"]
            tags = [t["name"] for t in item["tags"] if t["rank"] >= MIN_TAG_RANK]
            studios = [n["name"] for n in item["studios"]["nodes"]]
            rows.append(
                {
                    "uid": f"anilist:{item['id']}",
                    "category": category,
                    "media_group": "manga" if category == "manga" else "anime",
                    "name_ja": title["native"] or "",
                    "name_romaji": title["romaji"] or "",
                    "name_en": title["english"] or "",
                    "format": item["format"],
                    "release_year": (item["startDate"] or {}).get("year"),
                    "status": item["status"],
                    "source_material": item["source"] or "",
                    "genres": "|".join(item["genres"]),
                    "tags": "|".join(tags),
                    "episodes": item["episodes"],
                    "chapters": item["chapters"],
                    "volumes": item["volumes"],
                    "duration_min": item["duration"],
                    "studio": studios[0] if studios else "",
                    "popularity_metric": "anilist_popularity",
                    "popularity": item["popularity"],
                    "favourites": item["favourites"],
                    "average_score": item["averageScore"],
                    "rank_in_category": rank,
                    "links": [
                        e["node"]["id"]
                        for e in item["relations"]["edges"]
                        if e["relationType"] in LINK_TYPES
                    ],
                    "model_eligible": 1,
                }
            )
    return rows


def wikidata_rows(data: dict[str, list[dict]], anilist_names: set[str]) -> list[dict]:
    rows = []
    for category, items in data.items():
        kept = 0
        for item in items:
            if norm_name(item["ja"]) in anilist_names or kept >= PER_CATEGORY:
                continue  # already present as an anime/manga title, or past the top 500
            kept += 1
            rows.append(
                {
                    "uid": f"wikidata:{item['id']}",
                    "category": category,
                    "media_group": "live_action",
                    "name_ja": item["ja"],
                    "name_romaji": "",
                    "name_en": item["en"],
                    "format": "TV_SERIES" if category == "jp_tv_series" else "FILM",
                    "release_year": item.get("year"),
                    "genres": item.get("genres", ""),
                    "tags": "",
                    "popularity_metric": "wikipedia_sitelinks",
                    "popularity": item["sitelinks"],
                    "rank_in_category": kept,
                    "links": [],
                    "model_eligible": 0,  # no tag / episode features to learn from
                }
            )
    return rows


def franchise_groups(frame: pd.DataFrame) -> pd.Series:
    """Union-find over AniList relations so a franchise lives entirely in train or test."""
    parent = {uid: uid for uid in frame["uid"]}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for uid, links in zip(frame["uid"], frame["links"], strict=True):
        for other in links:
            target = f"anilist:{other}"
            if target in parent:
                parent[find(uid)] = find(target)
    return frame["uid"].map(find)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    anilist = fetch_anilist()
    wikidata = fetch_wikidata()
    rows = anilist_rows(anilist)
    names = {norm_name(r["name_ja"]) for r in rows}
    rows += wikidata_rows(wikidata, names)
    frame = pd.DataFrame(rows)

    # A title can top both the series and movie lists only if AniList mis-files it; keep first.
    frame = frame.drop_duplicates("uid").reset_index(drop=True)
    frame["franchise_group"] = franchise_groups(frame)

    splitter = StratifiedGroupKFold(n_splits=TEST_FRACTION_FOLDS, shuffle=True, random_state=SEED)
    _, test_idx = next(splitter.split(frame, frame["category"], groups=frame["franchise_group"]))
    frame["split"] = "train"
    frame.loc[test_idx, "split"] = "test"

    # Join India state-lift summary for titles that also appear in the Trends state table.
    state = pd.read_csv(STATE_TABLE, usecols=["title_id", "lift", "state"])
    summary = state.groupby("title_id").agg(
        india_lift_mean=("lift", "mean"), india_states=("state", "nunique")
    )
    frame = frame.merge(summary, how="left", left_on="uid", right_index=True)

    frame["links"] = frame["links"].map(lambda ids: "|".join(map(str, ids)))
    frame.to_csv(DATASET, index=False)

    test_share = (frame["split"] == "test").mean()
    print(frame.groupby(["category", "split"]).size().unstack().to_string())
    print(
        f"rows={len(frame)} test_share={test_share:.3f} "
        f"with_ja_and_en={int(((frame.name_ja != '') & (frame.name_en != '')).sum())} "
        f"state_table_overlap={int(frame['india_lift_mean'].notna().sum())}"
    )


if __name__ == "__main__":
    main()
