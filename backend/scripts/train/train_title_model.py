"""Train and honestly evaluate a content-DNA model on data/training/super_training_dataset.csv.

Task: from content features only (genres, tags, format, year, length, source material, studio,
category) predict a title's global audience size -- log10(AniList popularity) -- and its
community score. Popularity, favourites, score and rank are never used as inputs.

Protocol (no test-set peeking):
  * `split` column fixes 75% train / 25% test; franchises never straddle it.
  * Hyper-parameters are chosen by grouped, category-stratified 5-fold CV on the train split only.
  * The chosen model is refit on all train rows and scored ONCE on the test split.
  * Baselines: category median, ridge regression. Extra checks: group bootstrap CI on test,
    shuffled-label control (must score ~0), and a skill score versus the category median.

Live-action rows (Wikidata) carry no tags / length, so they stay in the dataset but are not
modelled (`model_eligible` = 0).

Run from the repository root:  .venv/bin/python backend/scripts/train/train_title_model.py
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parents[3]  # repository root
OUT_DIR = ROOT / "data/training"
DATASET = OUT_DIR / "super_training_dataset.csv"
SEED = 7
MIN_TAG_COUNT = 15
TOP_STUDIOS = 25
BOOTSTRAPS = 1000

GRID = {
    "max_depth": [2, 3, 5],
    "min_child_weight": [3, 10],
    "n_estimators": [150, 400],
}
BASE_PARAMS = dict(
    learning_rate=0.04,
    subsample=0.8,
    colsample_bytree=0.5,
    reg_lambda=5.0,
    random_state=SEED,
    n_jobs=4,
)
TARGETS = {
    "log10_popularity": lambda d: np.log10(d["popularity"].astype(float)),
    "average_score": lambda d: d["average_score"].astype(float),
}


def split_pipes(series: pd.Series) -> list[list[str]]:
    return [[t for t in str(v).split("|") if t] if pd.notna(v) else [] for v in series]


class Features:
    """Fit the vocabulary on train rows only, then encode any frame identically."""

    def __init__(self, train: pd.DataFrame):
        self.genres = sorted({g for row in split_pipes(train["genres"]) for g in row})
        counts = pd.Series([t for row in split_pipes(train["tags"]) for t in row]).value_counts()
        self.tags = sorted(counts[counts >= MIN_TAG_COUNT].index)
        self.studios = list(
            train["studio"].replace("", np.nan).value_counts().head(TOP_STUDIOS).index
        )
        self.sources = sorted(train["source_material"].fillna("").unique())
        self.categories = sorted(train["category"].unique())
        self.formats = sorted(train["format"].unique())
        self.columns = self.encode(train).columns.tolist()

    def encode(self, frame: pd.DataFrame) -> pd.DataFrame:
        genre_rows = split_pipes(frame["genres"])
        tag_rows = split_pipes(frame["tags"])
        out: dict[str, np.ndarray | pd.Series] = {}
        for g in self.genres:
            out[f"genre:{g}"] = np.array([g in row for row in genre_rows], dtype=float)
        for t in self.tags:
            out[f"tag:{t}"] = np.array([t in row for row in tag_rows], dtype=float)
        for s in self.studios:
            out[f"studio:{s}"] = (frame["studio"] == s).astype(float).to_numpy()
        for s in self.sources:
            out[f"source:{s}"] = (frame["source_material"].fillna("") == s).astype(float).to_numpy()
        for c in self.categories:
            out[f"category:{c}"] = (frame["category"] == c).astype(float).to_numpy()
        for f in self.formats:
            out[f"format:{f}"] = (frame["format"] == f).astype(float).to_numpy()
        for number in ["release_year", "episodes", "chapters", "volumes", "duration_min"]:
            out[number] = frame[number].astype(float).to_numpy()
        out["n_genres"] = np.array([len(r) for r in genre_rows], dtype=float)
        out["n_tags"] = np.array([len(r) for r in tag_rows], dtype=float)
        out["ongoing"] = (frame["status"] == "RELEASING").astype(float).to_numpy()
        return pd.DataFrame(out, index=frame.index)


def metrics(
    y_true: np.ndarray, y_pred: np.ndarray, category: np.ndarray, baseline: np.ndarray
) -> dict:
    within = []
    for cat in np.unique(category):
        mask = category == cat
        if mask.sum() >= 10 and np.ptp(y_pred[mask]) > 0:
            within.append(float(spearmanr(y_true[mask], y_pred[mask])[0]))
    sse_model = float(np.sum((y_true - y_pred) ** 2))
    sse_base = float(np.sum((y_true - baseline) ** 2))
    return {
        "r2": round(float(r2_score(y_true, y_pred)), 4),
        "rmse": round(float(np.sqrt(np.mean((y_true - y_pred) ** 2))), 4),
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 4),
        "spearman_within_category": round(float(np.mean(within)), 4) if within else 0.0,
        "skill_vs_category_median": round(1 - sse_model / sse_base, 4),
    }


def category_median(train: pd.DataFrame, y_train: np.ndarray, frame: pd.DataFrame) -> np.ndarray:
    medians = pd.Series(y_train, index=train.index).groupby(train["category"]).median()
    return frame["category"].map(medians).to_numpy(float)


def cross_validated_rmse(X, y, groups, strata, params) -> float:
    folds = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    errors = []
    for fit_idx, val_idx in folds.split(X, strata, groups=groups):
        model = XGBRegressor(**BASE_PARAMS, **params).fit(X.iloc[fit_idx], y[fit_idx])
        errors.append(np.mean((y[val_idx] - model.predict(X.iloc[val_idx])) ** 2))
    return float(np.sqrt(np.mean(errors)))


def group_bootstrap(y, pred, base, groups, category, rng) -> dict:
    unique = np.unique(groups)
    index_of = {g: np.flatnonzero(groups == g) for g in unique}
    r2s, skills = [], []
    for _ in range(BOOTSTRAPS):
        pick = rng.choice(unique, size=len(unique), replace=True)
        idx = np.concatenate([index_of[g] for g in pick])
        r2s.append(r2_score(y[idx], pred[idx]))
        skills.append(1 - np.sum((y[idx] - pred[idx]) ** 2) / np.sum((y[idx] - base[idx]) ** 2))
    return {
        "r2_95ci": [
            round(float(np.percentile(r2s, 2.5)), 3),
            round(float(np.percentile(r2s, 97.5)), 3),
        ],
        "skill_95ci": [
            round(float(np.percentile(skills, 2.5)), 3),
            round(float(np.percentile(skills, 97.5)), 3),
        ],
    }


def evaluate_target(
    name: str, data: pd.DataFrame, rng: np.random.Generator
) -> tuple[dict, XGBRegressor, Features]:
    frame = data.dropna(subset=["average_score"]) if name == "average_score" else data
    train = frame[frame["split"] == "train"]
    test = frame[frame["split"] == "test"]
    features = Features(train)
    X_train, X_test = features.encode(train), features.encode(test)
    y_train = TARGETS[name](train).to_numpy()
    y_test = TARGETS[name](test).to_numpy()
    groups = train["franchise_group"].to_numpy()

    best_params, best_cv = None, np.inf
    for values in itertools.product(*GRID.values()):
        params = dict(zip(GRID, values, strict=True))
        cv = cross_validated_rmse(X_train, y_train, groups, train["category"].to_numpy(), params)
        if cv < best_cv:
            best_params, best_cv = params, cv

    model = XGBRegressor(**BASE_PARAMS, **best_params).fit(X_train, y_train)
    test_pred = model.predict(X_test)
    base_test = category_median(train, y_train, test)
    category = test["category"].to_numpy()

    scaler = StandardScaler().fit(X_train.fillna(0))
    ridge = RidgeCV(alphas=np.logspace(-1, 3, 12)).fit(scaler.transform(X_train.fillna(0)), y_train)
    ridge_pred = ridge.predict(scaler.transform(X_test.fillna(0)))

    # Control: same pipeline on shuffled train labels must not beat the category median.
    shuffled = rng.permutation(y_train)
    control = XGBRegressor(**BASE_PARAMS, **best_params).fit(X_train, shuffled)
    control_pred = control.predict(X_test)

    importance = pd.Series(model.feature_importances_, index=X_train.columns).sort_values(
        ascending=False
    )
    result = {
        "rows": {"train": len(train), "test": len(test)},
        "chosen_params": best_params,
        "cv_rmse_train_only": round(best_cv, 4),
        "test": {
            "xgboost": metrics(y_test, test_pred, category, base_test),
            "ridge": metrics(y_test, ridge_pred, category, base_test),
            "category_median": metrics(y_test, base_test, category, base_test),
            "shuffled_label_control": metrics(y_test, control_pred, category, base_test),
        },
        "bootstrap_xgboost": group_bootstrap(
            y_test, test_pred, base_test, test["franchise_group"].to_numpy(), category, rng
        ),
        "top_features": {k: round(float(v), 4) for k, v in importance.head(10).items()},
    }
    predictions = test[["uid", "category", "name_ja", "name_en"]].copy()
    predictions["actual"] = np.round(y_test, 4)
    predictions["predicted"] = np.round(test_pred, 4)
    predictions.to_csv(OUT_DIR / f"test_predictions_{name}.csv", index=False)
    return result, model, features


def main() -> None:
    rng = np.random.default_rng(SEED)
    data = pd.read_csv(DATASET, keep_default_na=False, na_values=[""])
    data["source_material"] = data["source_material"].fillna("")
    eligible = data[data["model_eligible"] == 1].copy()

    # Leakage guards the report depends on.
    spanning = (eligible.groupby("franchise_group")["split"].nunique() > 1).sum()
    assert spanning == 0, "a franchise straddles train and test"
    assert eligible["uid"].is_unique

    report: dict = {
        "dataset": str(DATASET.relative_to(ROOT)),
        "rows_total": len(data),
        "rows_modelled": len(eligible),
        "split": data["split"].value_counts().to_dict(),
        "test_fraction": round(float((data["split"] == "test").mean()), 4),
        "note": (
            "Target is GLOBAL AniList audience size, restricted to each category's top-500 "
            "titles (range-restricted), not India-specific demand."
        ),
        "targets": {},
    }
    for name in TARGETS:
        result, model, _ = evaluate_target(name, eligible, rng)
        report["targets"][name] = result
        model.save_model(OUT_DIR / f"title_model_{name}.json")

    (OUT_DIR / "title_model_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    pop = report["targets"]["log10_popularity"]["test"]
    print(
        f"PROOF: {report['rows_total']} titles ({report['split']}), {report['rows_modelled']} modelled; "
        f"25% held-out test, franchise-grouped: log10-popularity XGBoost R2={pop['xgboost']['r2']} "
        f"skill-vs-category-median={pop['xgboost']['skill_vs_category_median']} "
        f"within-category rho={pop['xgboost']['spearman_within_category']} "
        f"(ridge R2={pop['ridge']['r2']}, shuffled-label control R2={pop['shuffled_label_control']['r2']})"
    )


if __name__ == "__main__":
    main()
