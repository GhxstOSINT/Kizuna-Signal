"""Collect AniList anime, clean it, and write a training-ready feature/label dataset.

python scripts/build_anilist_dataset.py --pages 20 --out data/processed
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.anilist import AniListClient, AniListError, records_from_envelope  # noqa: E402
from app.ml.dataset import assert_no_leakage, clean, split  # noqa: E402
from app.ml.titles import to_title_records  # noqa: E402


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=20)
    ap.add_argument("--per-page", type=int, default=50)
    ap.add_argument(
        "--start-year-from", type=int, help="keep titles starting in or after this year"
    )
    ap.add_argument("--start-year-to", type=int, help="keep titles starting in or before this year")
    ap.add_argument(
        "--sort",
        choices=["id", "popularity"],
        default="id",
        help="popularity = most popular first (titles with India search signal)",
    )
    ap.add_argument("--out", type=Path, default=Path("data/processed"))
    args = ap.parse_args()

    filters = {"status": "FINISHED"}
    if args.start_year_from:
        filters["startDateGreater"] = args.start_year_from * 10000 - 1
    if args.start_year_to:
        filters["startDateLesser"] = (args.start_year_to + 1) * 10000
    if args.sort == "popularity":
        filters["sort"] = ["POPULARITY_DESC"]
    records, live, cached = [], 0, 0
    try:
        for env in AniListClient().iter_pages(args.pages, args.per_page, **filters):
            records += records_from_envelope(env)
            cached += env["from_cache"]
            live += not env["from_cache"]
    except AniListError as exc:
        print(f"AniList failed: {exc}", file=sys.stderr)
        if not records:
            return 1
        print("continuing with partial data collected so far", file=sys.stderr)

    kept, dropped = clean(records)
    features, labels = split(kept)
    assert_no_leakage(features)

    args.out.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.out / "anilist_features.jsonl", features)
    write_jsonl(args.out / "anilist_labels.jsonl", labels)
    write_jsonl(
        args.out / "titles.jsonl", [t.model_dump(mode="json") for t in to_title_records(kept)]
    )
    report = {
        "fetched": len(records),
        "kept": len(kept),
        "dropped": dropped,
        "pages_live": live,
        "pages_cached": cached,
    }
    (args.out / "anilist_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
