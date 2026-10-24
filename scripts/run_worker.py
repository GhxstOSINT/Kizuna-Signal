"""Worker: runs queued state analyses, SEO jobs and source-collection jobs.

    python scripts/run_worker.py            # poll until stopped
    python scripts/run_worker.py --once     # drain the queue and exit
"""
import argparse
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.google_trends import TrendsClient  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.ml.state_model import StateModel  # noqa: E402
from app.services import worker  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", type=Path, default=Path("models"))
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--poll-s", type=float, default=5.0)
    args = ap.parse_args()

    try:
        model = StateModel.load(args.models)
    except FileNotFoundError:
        model = None  # SEO and collection jobs still run; analyses wait for a trained model
    print(f"worker using {model.version if model else 'no state model'}", flush=True)
    trends = TrendsClient()
    while True:
        with SessionLocal() as db:
            done = worker.process_all(db, model, trends)
        if any(done.values()):
            print(f"processed {done}", flush=True)
        if args.once:
            return 0
        time.sleep(args.poll_s)


if __name__ == "__main__":
    raise SystemExit(main())
