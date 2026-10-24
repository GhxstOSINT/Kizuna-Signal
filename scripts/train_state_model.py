"""Train the state model on the csv/ tables (see csv/data_dictionary.csv).

    python scripts/train_state_model.py

Encoder: every title in titles_features.csv. Labels: title x state shares; the model learns `lift`.
Saves models/state/<version>/ and updates models/state/LATEST.json.
"""

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault(
    "OPENBLAS_NUM_THREADS", "1"
)  # avoid allocation failures beside the collectors
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml import csv_data  # noqa: E402
from app.ml.embeddings import get_embedder  # noqa: E402
from app.ml.state_model import StateModel  # noqa: E402
from app.ml.states import STATES  # noqa: E402
from app.ml.success import SuccessModel  # noqa: E402
from app.ml.synthetic import SyntheticConfig  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=Path("csv"))
    ap.add_argument("--out", type=Path, default=Path("models"))
    ap.add_argument(
        "--embedder", choices=["auto", "tfidf", "sentence-transformers"], default="auto"
    )
    ap.add_argument("--folds", type=int, default=3)
    ap.add_argument(
        "--no-synthetic", action="store_true", help="train on real title x state rows only"
    )
    ap.add_argument(
        "--synthetic-weight",
        type=float,
        default=SyntheticConfig.weight,
        help="sample weight of synthetic rows (real rows = 1)",
    )
    args = ap.parse_args()

    data = csv_data.load(args.csv)
    print("csv checks:", json.dumps(data.check), flush=True)
    if (
        data.check["max_abs_lift_diff"] > 1e-6
        or data.check["labelled_titles_missing_features"]
        or not data.check["demand_columns_all_pre"]
    ):
        print("csv failed its consistency checks; not training", file=sys.stderr)
        return 1
    model = StateModel.train(
        data.titles,
        data.labels,
        list(STATES),
        demand=data.demand,
        state_ctx=data.state_ctx,
        embedder=get_embedder(args.embedder),
        n_folds=args.folds,
        synthetic=None if args.no_synthetic else SyntheticConfig(weight=args.synthetic_weight),
    )
    folder = model.save(args.out)
    print(f"saved {folder}")
    success = SuccessModel.from_csv(model, args.csv)
    if (
        success is not None
    ):  # cache the 0-100 rating reference so the API does not build it on the first request
        ref = success.reference_scores(model, folder)
        print(f"rating reference: {len(ref)} titles, raw score {ref.min():.1f}-{ref.max():.1f}")
    print(json.dumps(model.report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
