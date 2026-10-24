"""Initial India state-level training run.

Needs data/processed/titles.jsonl (build_anilist_dataset.py) and
data/processed/state_labels.csv with columns title_id,state,share (from the Trends step).

    python scripts/train_initial.py --n-titles 100
"""

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault(
    "OPENBLAS_NUM_THREADS", "1"
)  # avoid allocation failures beside the collectors
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.embeddings import get_embedder  # noqa: E402
from app.ml.features import titles_frame  # noqa: E402
from app.ml.schema import TitleRecord  # noqa: E402
from app.ml.states import PILOT_STATES, STATES  # noqa: E402
from app.ml.train import run, save  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("data/processed"))
    ap.add_argument("--n-titles", type=int, default=100)
    ap.add_argument("--out", type=Path, default=Path("models"))
    ap.add_argument("--states", choices=["pilot", "all"], default="pilot")
    ap.add_argument(
        "--embedder", choices=["auto", "tfidf", "sentence-transformers"], default="auto"
    )
    args = ap.parse_args()

    labels_path = args.data / "state_labels.csv"
    if not labels_path.exists():
        print(f"missing {labels_path}: run the Google Trends collection first", file=sys.stderr)
        return 1
    records = [
        TitleRecord(**json.loads(line))
        for line in (args.data / "titles.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    titles = titles_frame(records)
    labels = pd.read_csv(labels_path)
    ids = labels["title_id"].drop_duplicates().head(args.n_titles)
    states = PILOT_STATES if args.states == "pilot" else list(STATES)
    demand_path = args.data / "trends_demand.csv"
    demand = pd.read_csv(demand_path) if demand_path.exists() else None
    report, objects, _ = run(
        titles,
        labels[labels["title_id"].isin(ids)],
        states,
        demand=demand,
        embedder=get_embedder(args.embedder),
    )
    folder = save(report, args.out, objects)
    print(f"saved model to {folder}")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
