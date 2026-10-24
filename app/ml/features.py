"""Feature layer: content features per title, joined to (title, state) rows.

Versioned: bump FEATURE_VERSION whenever a definition changes. Everything fitted
(TF-IDF, SVD, vocabularies) is fitted on training titles only.
"""
import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer

FEATURE_VERSION = "content-v1"
LEAKY_COLUMNS = {"popularity", "favourites", "average_score", "log_popularity", "status", "share"}


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

    def __init__(self, svd_dims: int = 12, max_themes: int = 40):
        self.svd_dims, self.max_themes = svd_dims, max_themes

    def fit(self, titles: pd.DataFrame) -> "ContentEncoder":
        self.genres_ = sorted({g for gs in titles["genres"] for g in gs})
        counts = pd.Series([t for ts in titles["themes"] for t in ts]).value_counts()
        self.themes_ = list(counts.head(self.max_themes).index)
        self.formats_ = sorted(titles["format"].unique())
        self.tfidf_ = TfidfVectorizer(stop_words="english", min_df=2, max_features=2000)
        matrix = self.tfidf_.fit_transform(titles["synopsis"])
        dims = max(1, min(self.svd_dims, matrix.shape[0] - 1, matrix.shape[1] - 1))
        self.svd_ = TruncatedSVD(dims, random_state=0).fit(matrix)
        return self

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
        emb = self.svd_.transform(self.tfidf_.transform(titles["synopsis"]))
        for i in range(emb.shape[1]):
            cols[f"dna_{i}"] = emb[:, i]
        return pd.DataFrame(cols)


def build_rows(content: pd.DataFrame, labels: pd.DataFrame, states: list[str],
               state_context: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per (title, state). `labels` has title_id, state, share."""
    rows = labels[labels["state"].isin(states)].merge(content, on="title_id", how="inner")
    for s in states:
        rows[f"state_{s}"] = (rows["state"] == s).astype(int)
    if state_context is not None:
        rows = rows.merge(state_context, on="state", how="left")
    return rows


def feature_columns(rows: pd.DataFrame) -> list[str]:
    cols = [c for c in rows.columns if c not in {"title_id", "state"} | LEAKY_COLUMNS]
    assert_no_leakage(cols)
    return cols


def assert_no_leakage(columns: list[str]) -> None:
    leaked = LEAKY_COLUMNS & set(columns)
    if leaked:
        raise ValueError(f"outcome columns in feature set: {sorted(leaked)}")
