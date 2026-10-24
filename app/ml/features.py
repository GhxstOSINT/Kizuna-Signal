"""Feature layer: content features per title, joined to (title, state) rows.

Versioned: bump FEATURE_VERSION whenever a definition changes. Everything fitted
(TF-IDF, SVD, vocabularies) is fitted on training titles only.
"""
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

from app.ml.embeddings import TfidfSvdEmbedder

FEATURE_VERSION = "content-v2"

# Feature groups map to the architecture's model components.
GROUP_PREFIXES = {
    "content": ("genre_", "theme_", "format_", "log_episodes", "has_streaming", "dna_", "season_",
                "release_year", "has_prequel", "minutes"),
    "demand": ("pre_",),
    "regional": ("state_",),
    "comparable": ("cmp_", "parent_", "studio_"),
}


def group_columns(cols: list[str], *groups: str) -> list[str]:
    prefixes = tuple(p for g in groups for p in GROUP_PREFIXES[g])
    return [c for c in cols if c.startswith(prefixes)]
LEAKY_COLUMNS = {"popularity", "favourites", "average_score", "log_popularity", "status", "share",
                 "log_share", "dlog", "lift", "y"}


NON_FEATURE_COLUMNS = {"w", "is_synthetic", "n_content", "n_region"}  # row bookkeeping, never model inputs


def titles_frame(records) -> pd.DataFrame:
    return pd.DataFrame([{
        "title_id": r.title_id,
        "franchise_id": r.franchise_id,
        "release_date": pd.Timestamp(r.original_release_date) if r.original_release_date else pd.NaT,
        "format": r.format or "UNKNOWN",
        "genres": r.genres,
        "themes": r.themes,
        "episodes": r.runtime_or_episode_count.get("episodes"),
        "synopsis": r.synopsis or "",
        "has_streaming": bool(r.platform_or_distributor),
    } for r in records])


class ContentEncoder:
    """Fit on training titles; transform any title into a numeric row."""

    def __init__(self, embedder=None, dna_dims: int = 12, max_themes: int = 40, min_theme_titles: int = 1):
        self.embedder = embedder or TfidfSvdEmbedder()
        self.dna_dims, self.max_themes, self.min_theme_titles = dna_dims, max_themes, min_theme_titles

    def fit(self, titles: pd.DataFrame) -> "ContentEncoder":
        self.genres_ = sorted({g for gs in titles["genres"] for g in gs})
        counts = pd.Series([t for ts in titles["themes"] for t in ts]).value_counts()
        self.themes_ = list(counts[counts >= self.min_theme_titles].head(self.max_themes).index)
        self.formats_ = sorted(titles["format"].unique())
        self.embedder.fit(titles["synopsis"].tolist())
        emb = self.embedder.embed(titles["synopsis"].tolist())
        self.pca_ = PCA(max(1, min(self.dna_dims, emb.shape[0] - 1, emb.shape[1])), random_state=0).fit(emb)
        return self

    def embed(self, titles: pd.DataFrame) -> np.ndarray:
        """Unit vectors used for comparable retrieval."""
        return self.embedder.embed(titles["synopsis"].tolist())

    def transform(self, titles: pd.DataFrame) -> pd.DataFrame:
        cols = {"title_id": titles["title_id"].values}
        for g in self.genres_:
            cols[f"genre_{g}"] = titles["genres"].map(lambda gs, g=g: int(g in gs)).values
        for t in self.themes_:
            cols[f"theme_{t}"] = titles["themes"].map(lambda ts, t=t: int(t in ts)).values
        for f in self.formats_:
            cols[f"format_{f}"] = (titles["format"] == f).astype(int).values
        cols["log_episodes"] = np.log1p(titles["episodes"].fillna(0).astype(float)).values
        cols["has_streaming"] = titles["has_streaming"].astype(int).values
        dna = self.pca_.transform(self.embed(titles))
        for i in range(dna.shape[1]):
            cols[f"dna_{i}"] = dna[:, i]
        return pd.DataFrame(cols)


def build_rows(content: pd.DataFrame, labels: pd.DataFrame, states: list[str],
               state_context: pd.DataFrame | None = None,
               demand: pd.DataFrame | None = None,
               comparable: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per (title, state). `labels` has title_id, state, share.

    `demand` holds pre-release Trends features per (title_id, state); every column
    other than the keys must start with "pre_" so post-release data cannot enter.
    """
    rows = labels[labels["state"].isin(states)].merge(content, on="title_id", how="inner")
    if demand is not None:
        bad = [c for c in demand.columns if c not in {"title_id", "state"} and not c.startswith("pre_")]
        if bad:
            raise ValueError(f"demand features must be pre-release (pre_*): {bad}")
        rows = rows.merge(demand, on=["title_id", "state"], how="left")
        rows[[c for c in demand.columns if c.startswith("pre_")]] = rows[
            [c for c in demand.columns if c.startswith("pre_")]].fillna(0)
    if comparable is not None:  # historical outcomes of older, similar titles (cmp_share)
        rows = rows.merge(comparable[["title_id", "state", "cmp_share"]], on=["title_id", "state"], how="left")
        rows["cmp_missing"] = rows["cmp_share"].isna().astype(int)
        rows["cmp_share"] = rows["cmp_share"].fillna(1 / len(states))
    for s in states:
        rows[f"state_{s}"] = (rows["state"] == s).astype(int)
    if state_context is not None:
        rows = rows.merge(state_context, on="state", how="left")
    return rows


def feature_columns(rows: pd.DataFrame) -> list[str]:
    cols = [c for c in rows.columns if c not in {"title_id", "state"} | LEAKY_COLUMNS | NON_FEATURE_COLUMNS]
    assert_no_leakage(cols)
    return cols


def assert_no_leakage(columns: list[str]) -> None:
    leaked = LEAKY_COLUMNS & set(columns)
    if leaked:
        raise ValueError(f"outcome columns in feature set: {sorted(leaked)}")
