"""Clean AniList records and split them into a leak-safe feature table and label table."""
import math

MIN_SYNOPSIS_CHARS = 40
# Only finished titles have outcomes that are meaningful as training labels.
LABELLED_STATUSES = {"FINISHED"}
ALLOWED_FORMATS = {"TV", "TV_SHORT", "MOVIE", "OVA", "ONA", "SPECIAL"}
OUTCOME_FIELDS = {"popularity", "favourites", "average_score", "log_popularity", "status"}


def clean(records: list[dict]) -> tuple[list[dict], dict[str, int]]:
    """Dedupe and drop unusable rows. Returns (kept, drop counts by reason)."""
    dropped: dict[str, int] = {}
    kept: dict[int, dict] = {}

    def drop(reason: str) -> None:
        dropped[reason] = dropped.get(reason, 0) + 1

    for r in records:
        f = r["features"]
        if r["status"] not in LABELLED_STATUSES:
            drop("not_finished")
        elif f["format"] not in ALLOWED_FORMATS:
            drop("unsupported_format")
        elif not f["synopsis"] or len(f["synopsis"]) < MIN_SYNOPSIS_CHARS:
            drop("short_or_missing_synopsis")
        elif not f["genres"]:
            drop("no_genres")
        elif not f["release_year"]:
            drop("no_release_year")
        elif not r["outcome"]["popularity"]:
            drop("no_popularity_label")
        elif r["anilist_id"] in kept:
            drop("duplicate")
            # keep the most recently collected copy
            if r["provenance"]["collected_at"] > kept[r["anilist_id"]]["provenance"]["collected_at"]:
                kept[r["anilist_id"]] = r
        else:
            kept[r["anilist_id"]] = r
    return list(kept.values()), dropped


def split(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """Feature rows and label rows, joined only by anilist_id.

    Outcome fields never enter the feature rows, so a predicted title cannot
    leak post-release information.
    """
    features, labels = [], []
    for r in records:
        features.append({
            "anilist_id": r["anilist_id"],
            "name_en": r["name_en"],
            **r["features"],
            "raw_checksum": r["provenance"]["raw_checksum"],
        })
        labels.append({
            "anilist_id": r["anilist_id"],
            "log_popularity": round(math.log1p(r["outcome"]["popularity"]), 4),
            **r["outcome"],
        })
    return features, labels


def assert_no_leakage(features: list[dict]) -> None:
    leaked = OUTCOME_FIELDS & {k for row in features for k in row}
    if leaked:
        raise ValueError(f"outcome fields in feature table: {sorted(leaked)}")
