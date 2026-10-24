"""Loads the csv/ training tables described in csv/data_dictionary.csv.

Title content comes from titles_features.csv (synopsis and franchise are needed for comparables),
share labels and state context from the title x state table and state_reference.csv. The global
outcome file (popularity, score) is never read: the dictionary marks it LEAKY.
"""
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from app.ml.state_features import state_context, with_dlog

SOURCE_FOOTER = re.compile(r"\s*\((?:Source|Written by)[^)]*\)\s*$", re.IGNORECASE)


@dataclass
class CsvData:
    titles: pd.DataFrame  # every title (content frame) - used to fit the content encoder
    labels: pd.DataFrame  # title_id, state, share
    demand: pd.DataFrame  # title_id, state, pre_* (pre-release only)
    state_ctx: pd.DataFrame
    check: dict  # consistency checks against the file's own lift column


def _split(value) -> list[str]:
    return [] if pd.isna(value) else [v for v in str(value).split("|") if v]


def load(folder: Path = Path("csv")) -> CsvData:
    read = lambda name: pd.read_csv(folder / name, encoding="utf-8-sig")  # noqa: E731
    feats, table, ref = read("titles_features.csv"), read("training_table_title_x_state.csv"), read("state_reference.csv")
    demand = read("title_state_demand_PRE_RELEASE.csv")

    titles = pd.DataFrame({
        "title_id": feats["title_id"], "franchise_id": feats["franchise_id"],
        "release_date": pd.to_datetime(feats["original_release_date"]),
        "format": feats["format"].fillna("UNKNOWN"),
        "genres": feats["genres"].map(_split), "themes": feats["tags"].map(_split),
        "episodes": feats["episodes"], "minutes": feats["minutes_per_episode"],
        "synopsis": feats["synopsis"].fillna("").map(lambda s: SOURCE_FOOTER.sub("", s)),
        "has_streaming": False,  # platforms are global distributors: the dictionary says CAUTION
        "studio": feats["studio"], "has_prequel": feats["has_prequel"].astype(bool),
    })
    labels = table[["title_id", "state", "share"]]

    # The file's lift must equal the documented formula; a mismatch means the table is not what we think.
    l = with_dlog(labels)
    mine = (l["log_share"] - l.groupby("title_id")["log_share"].transform("mean")
            - l.groupby("state")["log_share"].transform("mean") + l["log_share"].mean())
    check = {"rows": len(table), "titles": int(table["title_id"].nunique()),
             "max_abs_lift_diff": float(np.abs(mine.to_numpy() - table["lift"].to_numpy()).max()),
             "demand_columns_all_pre": all(c.startswith("pre_") for c in demand.columns
                                           if c not in {"title_id", "state"}),
             "labelled_titles_missing_features": sorted(set(table["title_id"]) - set(titles["title_id"]))}
    return CsvData(titles, labels, demand, state_context(ref), check)
