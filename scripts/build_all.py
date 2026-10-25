"""Run the whole data + model pipeline in order and write one manifest of every dataset.

    PYTHONPATH=.packages py -3.12 scripts/build_all.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = ("train_model.py", "train_regional.py", "score_synthetic.py")


def main() -> None:
    for step in STEPS:
        print(f"== {step}", flush=True)
        subprocess.run([sys.executable, str(ROOT / "scripts" / step)], check=True, cwd=ROOT)

    art, syn = ROOT / "app" / "ml" / "artifacts", ROOT / "data" / "synthetic"
    regional = json.loads((art / "regional_model.json").read_text(encoding="utf-8"))
    title_model = json.loads((art / "market_model.json").read_text(encoding="utf-8"))
    factors = json.loads((syn / "factor_summary.json").read_text(encoding="utf-8"))
    manifest = {
        "datasets": {
            "mock_titles": {"rows": len(list((ROOT / "data/mock").glob("*/title.json"))), "kind": "real/mock"},
            "labelled_released_titles": {"rows": title_model["metrics"]["real_rows"], "kind": "real (hand-set labels)"},
            "synthetic_market": {"rows": regional["dataset"]["rows"], "kind": "synthetic, census-weighted"},
            "synthetic_factor_scores": {"rows": factors["rows"], "kind": "derived from synthetic_market"},
        },
        "models": {
            "title_performance": {"loo_r2": title_model["metrics"]["loo_r2"], "usable": False},
            "regional_demand": {
                "version": regional["model_version"],
                "holdout_r2": regional["metrics"]["holdout_r2"],
                "real_data_spearman": regional["metrics"]["real_data_check"]["spearman"],
            },
        },
        "weighted_average_pct_overall": factors["overall"]["weighted_average_pct"],
        "consistency_checks": factors["consistency_checks"],
    }
    (ROOT / "data" / "MANIFEST.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
