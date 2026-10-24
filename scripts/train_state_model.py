"""Train the final state model on everything collected from AniList and Google Trends.

    python scripts/train_state_model.py

Encoder: all titles in titles.jsonl. Labels/demand: every title with Trends state labels.
Saves models/state/<version>/ and updates models/state/LATEST.json.
"""
import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")  # avoid allocation failures beside the collectors
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from app.ml.embeddings import get_embedder  # noqa: E402
from app.ml.features import titles_frame  # noqa: E402
from app.ml.schema import TitleRecord  # noqa: E402
from app.ml.state_model import StateModel  # noqa: E402
from app.ml.states import STATES  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("data/processed"))
    ap.add_argument("--out", type=Path, default=Path("models"))
    ap.add_argument("--embedder", choices=["auto", "tfidf", "sentence-transformers"], default="auto")
    ap.add_argument("--folds", type=int, default=3)
    args = ap.parse_args()

    labels_path = args.data / "state_labels.csv"
    if not labels_path.exists():
        print(f"missing {labels_path}: run the Trends collection first", file=sys.stderr)
        return 1
    records = [TitleRecord(**json.loads(line)) for line in
               (args.data / "titles.jsonl").read_text(encoding="utf-8").splitlines() if line]
    demand_path = args.data / "trends_demand.csv"
    model = StateModel.train(titles_frame(records), pd.read_csv(labels_path), list(STATES),
                             demand=pd.read_csv(demand_path) if demand_path.exists() else None,
                             embedder=get_embedder(args.embedder), n_folds=args.folds)
    folder = model.save(args.out)
    print(f"saved {folder}")
    print(json.dumps(model.report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
