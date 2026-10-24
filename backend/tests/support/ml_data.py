"""Synthetic title/label generator shared by the ML, predict and report tests.

Labels are planted (genre decides which states over-index), so tests built on this prove the
plumbing and leakage guards, not model quality.
"""

import numpy as np
import pandas as pd

from app.ml.schema import TitleRecord
from app.ml.states import PILOT_STATES

GENRES = ["Action", "Romance", "Comedy", "Mecha"]
WORDS = {
    "Action": "battle sword war hero",
    "Romance": "love school heart",
    "Comedy": "funny gag friends",
    "Mecha": "robot pilot giant",
}


def synthetic(n=60, seed=0):
    rng = np.random.default_rng(seed)
    records, labels = [], []
    for i in range(n):
        g = GENRES[i % 4]
        records.append(
            TitleRecord(
                title_id=f"t{i}",
                franchise_id=f"t{i}",
                genres=[g],
                themes=[g.lower()],
                format="TV",
                original_release_date=pd.Timestamp("2016-01-01").date() + pd.Timedelta(days=40 * i),
                synopsis=f"{WORDS[g]} story {WORDS[g]} adventure number {i}",
                runtime_or_episode_count={"episodes": 12},
            )
        )
        # genre decides which states over-index, plus noise
        boost = {s: (3.0 if PILOT_STATES.index(s) % 4 == i % 4 else 1.0) for s in PILOT_STATES}
        raw = np.array([boost[s] for s in PILOT_STATES]) * rng.uniform(0.8, 1.2, len(PILOT_STATES))
        for s, v in zip(PILOT_STATES, raw / raw.sum(), strict=True):
            labels.append({"title_id": f"t{i}", "state": s, "share": v})
    return records, pd.DataFrame(labels)
