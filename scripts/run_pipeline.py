"""Unattended pipeline: parallel Trends collection -> merge -> retrain -> regenerate charts.

    python scripts/run_pipeline.py --shards 3 --n-titles 150

* Starts N sharded collectors (disjoint titles, shared on-disk cache).
* A shard stopped by Google (circuit breaker) is restarted after a cooldown; the cache resumes it.
* Every --train-every minutes, once enough titles have labels, merges the shards, retrains
  on all states and rewrites results/. Create data/processed/STOP to finish gracefully.
* Progress is written to data/processed/pipeline.log and data/processed/pipeline_status.json.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def log(data: Path, message: str) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {message}"
    print(line, flush=True)
    with open(data / "pipeline.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def merge(data: Path, shards: int) -> int:
    """Combine shard outputs into the files training reads. Returns the number of labelled titles."""
    for src, dst in (("state_labels", "state_labels.csv"), ("trends_demand", "trends_demand.csv")):
        frames = []
        for i in range(shards):
            path = data / f"{src}.shard{i}.csv"
            if path.exists() and path.stat().st_size > 2:
                try:
                    frames.append(pd.read_csv(path))
                except pd.errors.EmptyDataError:
                    pass
        if frames:
            tmp = data / f"{dst}.tmp"
            pd.concat(frames, ignore_index=True).to_csv(tmp, index=False)
            os.replace(tmp, data / dst)  # atomic: training never reads a half-written file
    labels = data / "state_labels.csv"
    return int(pd.read_csv(labels)["title_id"].nunique()) if labels.exists() and labels.stat().st_size > 2 else 0


def train_and_plot(data: Path, n_titles: int) -> dict:
    out = {}
    for name, cmd in (("train", [PY, "scripts/train_initial.py", "--states", "all", "--n-titles", "100000",
                                 "--data", str(data), "--embedder", "auto"]),
                      ("plots", [PY, "scripts/analyze_regions.py", "--data", str(data)])):
        done = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        out[name] = done.returncode
        if done.returncode != 0:
            out[f"{name}_error"] = (done.stderr or done.stdout)[-600:]
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("data/processed"))
    ap.add_argument("--shards", type=int, default=3)
    ap.add_argument("--n-titles", type=int, default=150)
    ap.add_argument("--delay", default="6", help="seconds between requests per shard")
    ap.add_argument("--cooldown-min", type=float, default=30)
    ap.add_argument("--train-every", type=float, default=20)
    ap.add_argument("--min-titles", type=int, default=30)
    args = ap.parse_args()
    data = args.data
    env = {**os.environ, "TRENDS_DELAY_S": args.delay, "TRENDS_BACKOFF_S": "60"}

    procs: dict[int, subprocess.Popen | None] = {i: None for i in range(args.shards)}
    next_start = {i: 0.0 for i in range(args.shards)}
    done = {i: False for i in range(args.shards)}
    last_train, trained_at_titles = 0.0, 0
    log(data, f"pipeline start: {args.shards} shards, {args.n_titles} titles, delay {args.delay}s")

    while True:
        now = time.time()
        for i in procs:
            p = procs[i]
            if p is not None and p.poll() is not None:
                procs[i] = None
                if p.returncode == 0:
                    done[i] = True
                    log(data, f"shard {i} finished")
                else:
                    next_start[i] = now + args.cooldown_min * 60
                    log(data, f"shard {i} stopped (code {p.returncode}); restarting in {args.cooldown_min:.0f} min")
            if procs[i] is None and not done[i] and now >= next_start[i]:
                cmd = [PY, "-u", "scripts/collect_trends.py", "--states", "all", "--n-titles", str(args.n_titles),
                       "--shard", str(i), "--of", str(args.shards), "--max-requests", "100000",
                       "--data", str(data)]
                procs[i] = subprocess.Popen(cmd, cwd=ROOT, env=env,
                                            stdout=open(data / f"collect.shard{i}.log", "a"), stderr=subprocess.STDOUT)
                log(data, f"shard {i} started")

        finished = all(done.values()) or (data / "STOP").exists()
        if finished or now - last_train >= args.train_every * 60:
            titles = merge(data, args.shards)
            if titles >= args.min_titles and (titles >= trained_at_titles + 5 or finished):
                result = train_and_plot(data, titles)
                trained_at_titles = titles
                status = {"time": datetime.now().isoformat(timespec="seconds"), "labelled_titles": titles,
                          "shards_done": sum(done.values()), **result}
                (data / "pipeline_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
                log(data, f"trained on {titles} titles -> {result}")
            else:
                log(data, f"{titles} labelled titles so far (need {args.min_titles}); not training yet")
            last_train = now
        if finished:
            for p in procs.values():
                if p is not None:
                    p.terminate()
            log(data, "pipeline finished")
            return 0
        time.sleep(30)


if __name__ == "__main__":
    raise SystemExit(main())
