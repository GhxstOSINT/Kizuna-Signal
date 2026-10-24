"""Generate ~1.5M census-weighted synthetic rows and train the state-demand model.

    PYTHONPATH=.packages py -3.12 scripts/train_regional.py [rows]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.regional_train import main  # noqa: E402

if __name__ == "__main__":
    artifact = main(int(sys.argv[1]) if len(sys.argv) > 1 else 1_500_000)
    print({k: v for k, v in artifact["dataset"].items() if k != "state_genre_profile"})
    print(artifact["metrics"])
    print("conformal:", artifact["conformal"])
