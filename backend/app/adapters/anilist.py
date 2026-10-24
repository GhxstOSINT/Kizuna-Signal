"""AniList source adapter: collect, store raw, normalize.

AniList supplies synopsis, genres, tags, studio and format (pre-release features)
and popularity/favourites/score (historical outcomes only, never features).
"""

import hashlib
import html
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.core.config import settings

QUERY = """
query ($page: Int, $perPage: Int, $sort: [MediaSort], $status: MediaStatus,
       $startDateGreater: FuzzyDateInt, $startDateLesser: FuzzyDateInt) {
  Page(page: $page, perPage: $perPage) {
    pageInfo { currentPage hasNextPage }
    media(type: ANIME, isAdult: false, sort: $sort, status: $status,
          startDate_greater: $startDateGreater, startDate_lesser: $startDateLesser) {
      id
      idMal
      title { romaji english native }
      synonyms
      episodes
      duration
      externalLinks { site type }
      description(asHtml: false)
      genres
      tags { name }
      studios(isMain: true) { nodes { name } }
      format
      season
      seasonYear
      startDate { year month day }
      status
      relations { edges { relationType node { id type } } }
      popularity
      favourites
      averageScore
    }
  }
}
"""

_TAG_RE = re.compile(r"<[^>]+>")


class AniListError(RuntimeError):
    pass


class AniListClient:
    def __init__(
        self,
        raw_dir: Path | None = None,
        client: httpx.Client | None = None,
        max_retries: int | None = None,
        sleep=time.sleep,
    ):
        self.raw_dir = Path(raw_dir or settings.anilist_raw_dir)
        self.client = client or httpx.Client(timeout=settings.anilist_timeout_s)
        self.max_retries = settings.anilist_max_retries if max_retries is None else max_retries
        self._sleep = sleep

    # Raw layer: append-only, checksum-named files, one folder per request key.
    @staticmethod
    def _key(variables: dict) -> str:
        return hashlib.sha256(json.dumps(variables, sort_keys=True).encode()).hexdigest()[:16]

    def _cached(self, key: str) -> dict | None:
        folder = self.raw_dir / key
        if not folder.exists():
            return None
        files = sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime)
        if not files:
            return None
        envelope = json.loads(files[-1].read_text(encoding="utf-8"))
        age = (datetime.now(UTC) - datetime.fromisoformat(envelope["collected_at"])).total_seconds()
        return envelope if age < settings.anilist_cache_ttl_s else None

    def _store(self, key: str, variables: dict, body: bytes) -> dict:
        envelope = {
            "source": "anilist",
            "variables": variables,
            "collected_at": datetime.now(UTC).isoformat(),
            "checksum": hashlib.sha256(body).hexdigest(),
            "response": json.loads(body),
        }
        folder = self.raw_dir / key
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{envelope['checksum']}.json").write_text(json.dumps(envelope), encoding="utf-8")
        return envelope

    def fetch_page(self, page: int, per_page: int = 50, **filters) -> dict:
        """One page of media, from cache when fresh. Returns the raw envelope."""
        variables = {"page": page, "perPage": per_page, "sort": ["ID"], **filters}
        key = self._key({**variables, "q": hashlib.sha256(QUERY.encode()).hexdigest()[:8]})
        hit = self._cached(key)
        if hit is not None:
            return {**hit, "from_cache": True}
        return {**self._store(key, variables, self._post(variables)), "from_cache": False}

    def _post(self, variables: dict) -> bytes:
        """POST with timeout, bounded retries and exponential backoff."""
        last: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.client.post(
                    settings.anilist_url, json={"query": QUERY, "variables": variables}
                )
                if resp.status_code == 429:
                    last = AniListError("rate limited (429)")
                    self._sleep(min(float(resp.headers.get("Retry-After", 2**attempt)), 60))
                    continue
                if resp.status_code >= 500:
                    last = AniListError(f"server error {resp.status_code}")
                    self._sleep(2**attempt)
                    continue
                resp.raise_for_status()
                data = resp.json()
                if data.get("errors") or "data" not in data:
                    raise AniListError(f"graphql error: {data.get('errors')}")
                return resp.content
            except httpx.TransportError as exc:
                last = exc
                self._sleep(2**attempt)
        raise AniListError(f"AniList unavailable after {self.max_retries + 1} attempts: {last}")

    def iter_pages(self, max_pages: int, per_page: int = 50, **filters):
        """Yield raw envelopes, pacing live calls below AniList's rate limit."""
        for page in range(1, max_pages + 1):
            env = self.fetch_page(page, per_page, **filters)
            yield env
            if not env["response"]["data"]["Page"]["pageInfo"]["hasNextPage"]:
                return
            if not env["from_cache"]:
                self._sleep(settings.anilist_page_delay_s)


def clean_text(text: str | None) -> str | None:
    if not text:
        return None
    text = html.unescape(_TAG_RE.sub(" ", text))
    return re.sub(r"\s+", " ", text).strip() or None


def normalize(media: dict, collected_at: str, checksum: str) -> dict:
    """Canonical record. `features` are knowable pre-release; `outcome` is not."""
    start = media.get("startDate") or {}
    title = media.get("title") or {}
    studios = [n["name"] for n in (media.get("studios") or {}).get("nodes", [])]
    edges = (media.get("relations") or {}).get("edges", [])
    return {
        "anilist_id": media["id"],
        "name_en": title.get("english") or title.get("romaji"),
        "name_jp": title.get("native"),
        "name_romaji": title.get("romaji"),
        "features": {
            "synopsis": clean_text(media.get("description")),
            "genres": sorted(media.get("genres") or []),
            "tags": sorted({t["name"] for t in media.get("tags") or []}),
            "studio": studios[0] if studios else None,
            "format": media.get("format"),
            "season": media.get("season"),
            "release_year": start.get("year") or media.get("seasonYear"),
            "has_prequel": any(e["relationType"] == "PREQUEL" for e in edges),
        },
        "outcome": {
            "popularity": media.get("popularity"),
            "favourites": media.get("favourites"),
            "average_score": media.get("averageScore"),
        },
        "status": media.get("status"),
        "extra": {
            "mal_id": media.get("idMal"),
            "synonyms": media.get("synonyms") or [],
            "episodes": media.get("episodes"),
            "duration": media.get("duration"),
            "streaming": sorted(
                {
                    link["site"]
                    for link in media.get("externalLinks") or []
                    if link.get("type") == "STREAMING"
                }
            ),
            "start": [start.get("year"), start.get("month"), start.get("day")],
            "related_ids": sorted(
                {e["node"]["id"] for e in edges if e["node"].get("type") == "ANIME"}
            ),
        },
        "provenance": {"source": "anilist", "collected_at": collected_at, "raw_checksum": checksum},
    }


def records_from_envelope(envelope: dict) -> list[dict]:
    media = envelope["response"]["data"]["Page"]["media"]
    return [normalize(m, envelope["collected_at"], envelope["checksum"]) for m in media]
