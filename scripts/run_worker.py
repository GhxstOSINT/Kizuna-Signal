"""Worker: runs queued analyses with the latest state model.

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

from app.db.session import SessionLocal  # noqa: E402
from app.ml.state_model import StateModel  # noqa: E402
from app.services import state_scoring  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", type=Path, default=Path("models"))
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--poll-s", type=float, default=5.0)
    args = ap.parse_args()

    model = StateModel.load(args.models)
    print(f"worker using {model.version}", flush=True)
    while True:
        with SessionLocal() as db:
            done = state_scoring.process_queued(db, model)
        if done:
            print(f"processed {done} analyses", flush=True)
        if args.once:
            return 0
        time.sleep(args.poll_s)


if __name__ == "__main__":
    raise SystemExit(main())
