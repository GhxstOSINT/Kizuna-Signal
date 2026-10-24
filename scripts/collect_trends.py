"""Collect Google Trends for India states and write demand features + state labels.

Resumable: every response is cached, so re-running continues where it stopped.

    python scripts/collect_trends.py --n-titles 100 --states pilot
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


def save(data: Path, demand, labels, reports, client) -> dict:
    pd.DataFrame(demand).to_csv(data / "trends_demand.csv", index=False)
    pd.DataFrame(labels).to_csv(data / "state_labels.csv", index=False)
    summary = {"attempted": len(reports), "kept": len({r["title_id"] for r in labels}),
               "dropped": {r["title_id"]: r["error"] for r in reports if r["error"]},
               "live_requests": client.live_requests}
    (data / "trends_report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("data/processed"))
    ap.add_argument("--n-titles", type=int, default=100)
    ap.add_argument("--states", choices=["pilot", "all"], default="pilot")
    ap.add_argument("--max-requests", type=int)
    args = ap.parse_args()

    titles = [TitleRecord(**json.loads(line)) for line in
              (args.data / "titles.jsonl").read_text(encoding="utf-8").splitlines() if line]
    eligible = [t for t in titles if is_eligible(t, date.today())]
    print(f"{len(eligible)}/{len(titles)} titles have a complete 52-week post-release window")

    states = PILOT_STATES if args.states == "pilot" else list(STATES)
    client = TrendsClient(max_requests=args.max_requests)
    demand, labels, reports = [], [], []
    try:
        for title in eligible[: args.n_titles]:
            d, l, rep = collect_title(client, title, states)
            demand += d
            labels += l
            reports.append(rep)
            print(rep["title_id"], rep["states_ok"], rep["error"] or "ok", flush=True)
            save(args.data, demand, labels, reports, client)  # survive an interrupted run
    except QuotaExceeded as exc:
        print(f"stopped: {exc}", file=sys.stderr)

    summary = save(args.data, demand, labels, reports, client)
    print(json.dumps({k: v for k, v in summary.items() if k != "dropped"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
