"""Fetch measured AniList data for every comparable title and write data/real/comparables_anilist.json.

    PYTHONPATH=.packages py -3.12 scripts/fetch_real_comparables.py

`signal` = 0.6 * AniList average score + 0.4 * log-scaled popularity (same formula as the live
AniList adapter). It is a global popularity/quality measure, not India-specific viewership.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ml.corpus import comparable_names  # noqa: E402
from app.ml.levenshtein import name_similarity  # noqa: E402
from app.services.sources.live import MATCH_THRESHOLD, log_scale  # noqa: E402

OUT = ROOT / "data" / "real" / "comparables_anilist.json"
QUERY = """
query ($s: String) { Page(perPage: 6) { media(search: $s, type: ANIME) {
  id title { romaji english } format genres tags { name rank } averageScore popularity startDate { year }
} } }"""


def main() -> None:
    client = httpx.Client(timeout=20)
    rows, missed = [], []
    for name in comparable_names():
        for _attempt in range(3):
            r = client.post("https://graphql.anilist.co", json={"query": QUERY, "variables": {"s": name}})
            if r.status_code == 429:
                time.sleep(20)
                continue
            r.raise_for_status()
            break
        best = None
        for media in r.json()["data"]["Page"]["media"]:
            names = [n for n in (media["title"]["romaji"], media["title"]["english"]) if n]
            score = max(name_similarity(name, n) for n in names)
            if best is None or score > best[1]:
                best = (media, score)
        time.sleep(1.0)
        if best is None or best[1] < MATCH_THRESHOLD or not best[0]["averageScore"]:
            missed.append(name)
            continue
        media, match = best
        tags = sorted(media["tags"], key=lambda t: -t["rank"])[:8]
        signal = 0.6 * media["averageScore"] + 0.4 * log_scale(media["popularity"], 1_000_000)
        rows.append(
            {
                "title": name,
                "anilist_id": media["id"],
                "matched_title": media["title"]["romaji"],
                "match_similarity": round(match, 3),
                "format": media["format"],
                "year": media["startDate"]["year"],
                "genres": [g.lower() for g in media["genres"]],
                "themes": [t["name"].lower() for t in tags],
                "average_score": media["averageScore"],
                "popularity": media["popularity"],
                "signal": round(signal, 2),
            }
        )
        print(f"{name:32s} -> {media['title']['romaji']:32s} sim {match:.2f} signal {signal:.1f}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "source": "AniList GraphQL API (https://graphql.anilist.co)",
                "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "signal_formula": "0.6*averageScore + 0.4*log10(1+popularity)/log10(1+1e6)*100",
                "unmatched": missed,
                "titles": rows,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"\n{len(rows)} matched, unmatched: {missed}")


if __name__ == "__main__":
    main()
