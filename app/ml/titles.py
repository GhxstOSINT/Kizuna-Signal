"""Build TitleRecord rows from normalized AniList records."""
from datetime import date

from app.ml.schema import TitleRecord


def _franchise_roots(records: list[dict]) -> dict[int, int]:
    """Union titles linked by relations; the root is the smallest AniList id in the group."""
    parent = {r["anilist_id"]: r["anilist_id"] for r in records}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for r in records:
        for other in r["extra"]["related_ids"]:
            if other in parent:
                a, b = find(r["anilist_id"]), find(other)
                parent[max(a, b)] = min(a, b)
    return {i: find(i) for i in parent}


def _date(parts: list[int | None]) -> date | None:
    y, m, d = parts
    return date(y, m, d) if y and m and d else None


def to_title_records(records: list[dict]) -> list[TitleRecord]:
    roots = _franchise_roots(records)
    out = []
    for r in records:
        f, x = r["features"], r["extra"]
        source_ids: dict[str, str | int] = {"anilist": r["anilist_id"]}
        if x["mal_id"]:
            source_ids["mal"] = x["mal_id"]
        out.append(TitleRecord(
            title_id=f"anilist:{r['anilist_id']}",
            franchise_id=f"anilist:{roots[r['anilist_id']]}",
            original_title=r["name_jp"],
            english_title=r["name_en"],
            japanese_title=r["name_jp"],
            romanized_title=r["name_romaji"],
            source_ids=source_ids,
            genres=f["genres"],
            themes=f["tags"],
            format=f["format"],
            runtime_or_episode_count={"episodes": x["episodes"], "minutes_per_episode": x["duration"]},
            original_release_date=_date(x["start"]),
            platform_or_distributor=x["streaming"],
            synopsis=f["synopsis"],
        ))
    return out
