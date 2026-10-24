"""Collect Google Trends for India states and write demand features + state labels.

Resumable: every response is cached, so re-running continues where it stopped.
Shardable: `--shard 1 --of 3` takes every third title, writing its own output files, so
several processes can collect in parallel (see scripts/run_pipeline.py, which merges them).

    python scripts/collect_trends.py --n-titles 100 --states pilot
    python scripts/collect_trends.py --n-titles 150 --states all --shard 0 --of 3

Exit code 0 = all assigned titles done, 3 = stopped early (blocked or request budget used).
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.google_trends import QuotaExceeded, TrendsClient  # noqa: E402
from app.ml.demand import collect_title, is_eligible  # noqa: E402
from app.ml.schema import TitleRecord  # noqa: E402
from app.ml.states import PILOT_STATES, STATES  # noqa: E402


def names(shard: int | None) -> tuple[str, str, str]:
    suffix = "" if shard is None else f".shard{shard}"
    return f"trends_demand{suffix}.csv", f"state_labels{suffix}.csv", f"trends_report{suffix}.json"


def save(data: Path, shard, demand, labels, reports, client, assigned: int, complete: bool) -> dict:
    demand_f, labels_f, report_f = names(shard)
    pd.DataFrame(demand).to_csv(data / demand_f, index=False)
    pd.DataFrame(labels).to_csv(data / labels_f, index=False)
    summary = {"assigned": assigned, "attempted": len(reports), "complete": complete,
               "kept": len({r["title_id"] for r in labels}),
               "dropped": {r["title_id"]: r["error"] for r in reports if r["error"]},
               "live_requests": client.live_requests}
    (data / report_f).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("data/processed"))
    ap.add_argument("--n-titles", type=int, default=100)
    ap.add_argument("--states", choices=["pilot", "all"], default="pilot")
    ap.add_argument("--max-requests", type=int)
    ap.add_argument("--shard", type=int, help="0-based shard index")
    ap.add_argument("--of", type=int, default=1, help="number of shards")
    args = ap.parse_args()

    titles = [TitleRecord(**json.loads(line)) for line in
              (args.data / "titles.jsonl").read_text(encoding="utf-8").splitlines() if line]
    eligible = [t for t in titles if is_eligible(t, date.today())][: args.n_titles]
    mine = eligible[args.shard::args.of] if args.shard is not None else eligible
    print(f"shard {args.shard}: {len(mine)} titles of {len(eligible)}", flush=True)

    states = PILOT_STATES if args.states == "pilot" else list(STATES)
    client = TrendsClient(max_requests=args.max_requests)
    demand, labels, reports = [], [], []
    stopped = False
    try:
        for title in mine:
            d, lab, rep = collect_title(client, title, states)
            demand += d
            labels += lab
            reports.append(rep)
            print(rep["title_id"], rep["states_ok"], rep["error"] or "ok", flush=True)
            save(args.data, args.shard, demand, labels, reports, client, len(mine), False)
    except QuotaExceeded as exc:
        stopped = True
        print(f"stopped: {exc}", file=sys.stderr, flush=True)

    summary = save(args.data, args.shard, demand, labels, reports, client, len(mine), not stopped)
    print(json.dumps({k: v for k, v in summary.items() if k != "dropped"}, indent=2))
    return 3 if stopped else 0


if __name__ == "__main__":
    raise SystemExit(main())
