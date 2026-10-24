"""Features for the state model beyond content, following csv/data_dictionary.csv.

* Label: `lift` = log_share - title mean - state mean + grand mean (>0: the title over-performs in that
  state versus a typical anime there). State and grand means come from TRAINING titles only.
* History features borrow the title-centred log share (`dlog`) of titles whose full post-release
  window had already ended before this title launched: the same franchise (`parent_`), the same
  studio (`studio_`, shrunk towards 0) and similar older titles (`cmp_`).
* State context: region zone and dominant language one-hots (an approximation, see the dictionary).
"""
import numpy as np
import pandas as pd

from app.ml.comparables import ComparableIndex, comparable_features

LAG_DAYS = 365  # Trends label window is 52 weeks: an earlier title's outcome is known only after it
SEASONS = ["WINTER", "SPRING", "SUMMER", "FALL"]
PARENT_SHRINK, STUDIO_SHRINK = 1.0, 3.0


def season_of(ts: pd.Timestamp) -> str:
    return SEASONS[(ts.month % 12) // 3]


def with_dlog(labels: pd.DataFrame) -> pd.DataFrame:
    """Adds log_share and dlog (log share minus the title's own mean). Needs no other title."""
    out = labels.copy()
    out["log_share"] = np.log(out["share"].clip(lower=1e-6))
    out["dlog"] = out["log_share"] - out.groupby("title_id")["log_share"].transform("mean")
    return out


def state_effect(labels: pd.DataFrame) -> pd.Series:
    """mean log_share of each state minus the grand mean, from the given (training) labels only."""
    return labels.groupby("state")["log_share"].mean() - labels["log_share"].mean()


def add_lift(rows: pd.DataFrame, effect: pd.Series) -> pd.DataFrame:
    """y = lift = dlog - state effect. Unseen states get effect 0."""
    return rows.assign(y=rows["dlog"] - rows["state"].map(effect).fillna(0.0))


def title_extras(titles: pd.DataFrame) -> pd.DataFrame:
    """Season, year, sequel flag and length; tolerant of frames that lack the optional columns."""
    out = pd.DataFrame({"title_id": titles["title_id"].values})
    season = titles["release_date"].map(season_of)
    for s in SEASONS:
        out[f"season_{s}"] = (season == s).astype(int).values
    out["release_year"] = titles["release_date"].dt.year.values
    out["has_prequel"] = titles["has_prequel"].fillna(False).astype(int).values if "has_prequel" in titles else 0
    out["minutes"] = titles["minutes"].fillna(0).astype(float).values if "minutes" in titles else 0.0
    return out


def state_context(reference: pd.DataFrame) -> pd.DataFrame:
    """One row per state: region-zone and dominant-language indicators (all named state_*)."""
    out = reference[["state"]].copy()
    for col, prefix in (("region_zone", "state_zone_"), ("dominant_language_APPROX", "state_lang_")):
        dummies = pd.get_dummies(reference[col], prefix=prefix, prefix_sep="").astype(int)
        out = pd.concat([out, dummies], axis=1)
    return out


def _earlier_group_mean(targets: pd.DataFrame, pool: pd.DataFrame, dlog: pd.DataFrame, states: list[str],
                        key: str, shrink: float, prefix: str) -> pd.DataFrame:
    """Per (target, state): shrunk mean dlog of pool titles in the same `key` group that finished
    their label window before the target launched."""
    wide = dlog.pivot_table(index="title_id", columns="state", values="dlog").reindex(columns=states)
    rows = []
    for _, t in targets.iterrows():
        group = pool[pool[key].notna() & (pool[key] == t[key]) & (pool["title_id"] != t["title_id"])
                     & (pool["release_date"] + pd.Timedelta(days=LAG_DAYS) <= t["release_date"])] \
            if pd.notna(t[key]) else pool.iloc[0:0]
        block = wide.reindex(group["title_id"])
        n, total = block.notna().sum(), block.sum()
        for s in states:
            rows.append({"title_id": t["title_id"], "state": s,
                         f"{prefix}_dlog": float(total[s] / (n[s] + shrink)) if len(group) else 0.0,
                         f"{prefix}_n": int(n[s]) if len(group) else 0})
    return pd.DataFrame(rows)


def history_features(targets: pd.DataFrame, target_emb: np.ndarray, pool: pd.DataFrame, pool_emb: np.ndarray,
                     labels: pd.DataFrame, states: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """cmp_dlog (similar older titles), parent_dlog (same franchise), studio_dlog (same studio).

    `labels` must carry dlog. Returns (features per title x state, comparable stats per title).
    """
    cmp_rows, cmp_stats = comparable_features(ComparableIndex(pool, pool_emb), targets, target_emb,
                                              labels, states, value="dlog")
    cmp_rows = cmp_rows.rename(columns={"cmp_share": "cmp_dlog"})
    cmp_rows["cmp_n"] = cmp_rows["title_id"].map(cmp_stats.set_index("title_id")["cmp_count"])
    cmp_rows["cmp_dlog"] = cmp_rows["cmp_dlog"].fillna(0.0)
    studio = lambda f: f.assign(studio_key=f["studio"].str.strip().str.lower() if "studio" in f else np.nan)  # noqa: E731
    parent = _earlier_group_mean(targets, pool, labels, states, "franchise_id", PARENT_SHRINK, "parent")
    studios = _earlier_group_mean(studio(targets), studio(pool), labels, states, "studio_key", STUDIO_SHRINK, "studio")
    out = cmp_rows.merge(parent, on=["title_id", "state"]).merge(studios, on=["title_id", "state"])
    return out, cmp_stats
