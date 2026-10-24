"""Synthetic augmentation + state-affinity model for data/survey/training_table_title_x_state.csv.

Steps (all reproducible with a fixed seed):
  1. Winsorise the `lift` target with a robust (median / MAD) bound, so heavy-tail small-state
     rows do not dominate the fit.
  2. Smoothed bootstrap: each synthetic title is a perturbed copy of a real "template" title
     (tag / genre flips, release-year jitter). Its per-state lift is the template's lift plus
     Normal(0, tau * robust-sigma-of-that-state) noise, clipped to the same bound.
  3. Honest evaluation: GroupKFold by title on REAL rows only. Synthetic rows are generated from
     the training fold alone, so nothing leaks into the held-out titles.
  4. Compare weighted-average baselines against XGBoost (real only, real + synthetic).

Run from the repository root:  .venv/bin/python scripts/train_regional_model.py
Needs `pip install -e ".[ml]"` and, on macOS, `brew install libomp`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import r2_score
from sklearn.model_selection import GroupKFold
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.services.census import resolve_state  # noqa: E402

SOURCE = ROOT / "data/survey/training_table_title_x_state.csv"
OUT_DIR = ROOT / "data/training"
SYNTHETIC_CSV = OUT_DIR / "synthetic_title_x_state.csv"
MODEL_FILE = OUT_DIR / "regional_lift_xgb.json"
REPORT_FILE = OUT_DIR / "regional_model_report.json"

SEED = 7
FINAL_SYNTHETIC_ROWS = 100_000
FOLD_SYNTHETIC_PER_REAL = 20
MAD_BOUND = 4.0  # winsorise lift at median +/- 4 robust sigmas
NOISE_TAU = 0.35  # synthetic noise as a fraction of each state's robust sigma
FLIP_PROBABILITY = 0.03
MIN_STATES_FOR_RANK = 6

XGB_PARAMS = dict(
    n_estimators=300,
    max_depth=4,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.5,
    min_child_weight=10,
    reg_lambda=5.0,
    random_state=SEED,
    n_jobs=4,
)


def robust_bounds(values: pd.Series) -> tuple[float, float]:
    centre = float(values.median())
    sigma = 1.4826 * float((values - centre).abs().median())
    return centre - MAD_BOUND * sigma, centre + MAD_BOUND * sigma


def binary_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c.startswith(("genre_", "tag_"))]


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Numeric design matrix: content flags, release info, pre-release trend, state context."""
    out = df[binary_columns(df)].copy()
    out["release_year"] = df["release_year"]
    out["has_prequel"] = df["has_prequel"]
    out["episodes"] = df["episodes"].fillna(0)
    out["pre_has_data"] = df["pre_has_data"]
    out["pre_level"] = np.log1p(df["pre_level"])
    out["pre_growth"] = df["pre_growth"]
    out["pre_volatility"] = df["pre_volatility"]
    states = [resolve_state(name) for name in df["state_name"]]
    out["log_population"] = [np.log(s.population) if s else np.nan for s in states]
    out["urban_pct"] = [s.urban_pct if s else np.nan for s in states]
    for column, prefix in [("format", "fmt"), ("season", "season"), ("region_zone", "zone")]:
        out = out.join(pd.get_dummies(df[column], prefix=prefix, dtype=float))
    return out.join(pd.get_dummies(df["state"], prefix="st", dtype=float))


def state_sigma(train: pd.DataFrame) -> pd.DataFrame:
    """Per-state robust location and scale of the winsorised lift."""
    grouped = train.groupby("state")["lift_w"]
    centre = grouped.median()
    sigma = 1.4826 * grouped.apply(lambda s: (s - s.median()).abs().median())
    overall = float(sigma.median())
    return pd.DataFrame({"mu": centre, "sigma": sigma.fillna(overall).clip(lower=0.3)})


def synthesise(train: pd.DataFrame, rows: int, rng: np.random.Generator, bounds) -> pd.DataFrame:
    """Smoothed bootstrap of whole titles; keeps each template's real state coverage."""
    flags = binary_columns(train)
    stats = state_sigma(train)
    titles = {tid: group for tid, group in train.groupby("title_id")}
    ids = list(titles)
    pieces: list[pd.DataFrame] = []
    produced = 0
    serial = 0
    while produced < rows:
        template = titles[ids[rng.integers(len(ids))]].copy()
        flip = rng.random(len(flags)) < FLIP_PROBABILITY
        for name, do_flip in zip(flags, flip, strict=True):
            if do_flip:
                template[name] = 1 - template[name]
        template["release_year"] = template["release_year"] + int(rng.integers(-1, 2))
        sigma = stats.loc[template["state"], "sigma"].to_numpy()
        noisy = template["lift_w"].to_numpy() + rng.normal(0.0, NOISE_TAU * sigma)
        template["template_title_id"] = template["title_id"]
        template["title_id"] = f"synthetic:{serial:06d}"
        template["lift_w"] = np.clip(noisy, *bounds)
        template["is_synthetic"] = 1
        pieces.append(template)
        produced += len(template)
        serial += 1
    return pd.concat(pieces, ignore_index=True).iloc[:rows]


def rank_score(frame: pd.DataFrame, prediction: np.ndarray) -> float:
    """Mean Spearman of predicted vs actual lift across states, per held-out title."""
    scores = []
    for _, idx in frame.groupby("title_id").indices.items():
        if len(idx) >= MIN_STATES_FOR_RANK:
            if np.ptp(prediction[idx]) == 0:  # a constant predictor ranks nothing
                scores.append(0.0)
                continue
            scores.append(float(spearmanr(frame["lift"].to_numpy()[idx], prediction[idx])[0]))
    return float(np.mean(scores))


def similarity_weighted(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    """Weighted average of the state's past lifts, weighted by Jaccard content similarity."""
    flags = binary_columns(train)
    train_titles = train.drop_duplicates("title_id").set_index("title_id")[flags].to_numpy(bool)
    train_ids = train.drop_duplicates("title_id")["title_id"].to_numpy()
    index = {tid: i for i, tid in enumerate(train_ids)}
    by_state = {s: g for s, g in train.groupby("state")}
    test_flags = test.drop_duplicates("title_id").set_index("title_id")[flags]
    weights_for = {}
    for tid, row in test_flags.iterrows():
        vec = row.to_numpy(bool)
        inter = (train_titles & vec).sum(axis=1)
        union = (train_titles | vec).sum(axis=1)
        weights_for[tid] = inter / np.maximum(union, 1)
    global_mean = float(train["lift_w"].mean())
    out = np.empty(len(test))
    for i, (tid, state) in enumerate(zip(test["title_id"], test["state"], strict=True)):
        group = by_state.get(state)
        if group is None:
            out[i] = global_mean
            continue
        w = weights_for[tid][[index[t] for t in group["title_id"]]] ** 2 + 1e-3
        # shrink toward the global mean with 5 pseudo-observations
        out[i] = (np.dot(w, group["lift_w"]) + 5 * global_mean * w.mean()) / (
            w.sum() + 5 * w.mean()
        )
    return out


def matrix(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Feature matrix with a fixed column order; categories absent from `frame` become 0."""
    return add_features(frame).reindex(columns=columns, fill_value=0.0).fillna(0.0)


def fit_xgb(frame: pd.DataFrame, columns: list[str]) -> XGBRegressor:
    model = XGBRegressor(**XGB_PARAMS)
    model.fit(matrix(frame, columns), frame["lift_w"])
    return model


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    raw = pd.read_csv(SOURCE)
    low, high = robust_bounds(raw["lift"])
    raw["lift_w"] = raw["lift"].clip(low, high)
    raw["is_synthetic"] = 0
    raw["template_title_id"] = ""
    n_clipped = int((raw["lift"] != raw["lift_w"]).sum())
    columns = list(add_features(raw).columns)
    real = raw

    folds = GroupKFold(n_splits=5)
    results: dict[str, dict[str, list[float]]] = {
        name: {"rmse": [], "r2": [], "rank": []}
        for name in [
            "global_mean",
            "state_mean",
            "similarity_weighted",
            "xgb_real",
            "xgb_real_no_pre",
            "xgb_real_synth",
        ]
    }

    def record(name: str, test: pd.DataFrame, pred: np.ndarray) -> None:
        results[name]["rmse"].append(float(np.sqrt(np.mean((test["lift"] - pred) ** 2))))
        results[name]["r2"].append(float(r2_score(test["lift"], pred)))
        results[name]["rank"].append(rank_score(test.reset_index(drop=True), pred))

    for train_idx, test_idx in folds.split(real, groups=real["title_id"]):
        train = real.iloc[train_idx].reset_index(drop=True)
        test = real.iloc[test_idx].reset_index(drop=True)
        record("global_mean", test, np.full(len(test), train["lift_w"].mean()))
        state_mean = train.groupby("state")["lift_w"].mean()
        record(
            "state_mean",
            test,
            test["state"].map(state_mean).fillna(train["lift_w"].mean()).to_numpy(),
        )
        record("similarity_weighted", test, similarity_weighted(train, test))
        test_x = matrix(test, columns)
        record("xgb_real", test, fit_xgb(train, columns).predict(test_x))
        # Ablation: the pre_* columns mostly say "this state has measurable search volume".
        no_pre = [c for c in columns if not c.startswith("pre_")]
        record("xgb_real_no_pre", test, fit_xgb(train, no_pre).predict(test_x[no_pre]))
        bounds = robust_bounds(train["lift"])
        synth = synthesise(train, FOLD_SYNTHETIC_PER_REAL * len(train), rng, bounds)
        augmented = pd.concat([train, synth], ignore_index=True)
        record("xgb_real_synth", test, fit_xgb(augmented, columns).predict(test_x))

    summary = {
        name: {metric: round(float(np.mean(values)), 4) for metric, values in metrics.items()}
        for name, metrics in results.items()
    }

    # Final artefacts: the synthetic CSV (whole real table as the source) and the model.
    synthetic = synthesise(real, FINAL_SYNTHETIC_ROWS, rng, (low, high))
    synthetic["lift"] = synthetic["lift_w"]
    source_columns = list(pd.read_csv(SOURCE, nrows=0).columns)
    synthetic_out = synthetic[source_columns + ["template_title_id", "is_synthetic"]]
    synthetic_out.to_csv(SYNTHETIC_CSV, index=False)

    # Ship whichever variant ranks best on held-out real titles, not the one with most data.
    use_synthetic = summary["xgb_real_synth"]["rank"] > summary["xgb_real"]["rank"]
    final_frame = pd.concat([real, synthetic], ignore_index=True) if use_synthetic else real
    final_model = fit_xgb(final_frame, columns)
    final_model.save_model(MODEL_FILE)

    report = {
        "source": str(SOURCE.relative_to(ROOT)),
        "real_rows": len(raw),
        "real_titles": int(raw["title_id"].nunique()),
        "winsor_bounds": [round(low, 3), round(high, 3)],
        "rows_winsorised": n_clipped,
        "synthetic_rows": len(synthetic_out),
        "cv": "5-fold GroupKFold by title on real rows only; synthetic data built from train fold",
        "results": summary,
        "shipped_model": "xgb_real_synth" if use_synthetic else "xgb_real",
    }
    REPORT_FILE.write_text(json.dumps(report, indent=2) + "\n")

    shipped = summary[report["shipped_model"]]
    base = summary["state_mean"]
    print(json.dumps(report, indent=2))
    print(
        f"PROOF: {len(synthetic_out):,} synthetic rows from {len(raw)} real rows ({n_clipped} "
        f"winsorised); 5-fold held-out-title CV: shipped {report['shipped_model']} "
        f"R2={shipped['r2']}, per-title state rank-corr={shipped['rank']} vs state-mean "
        f"baseline R2={base['r2']}, rank-corr={base['rank']}; xgb_real_synth "
        f"R2={summary['xgb_real_synth']['r2']}, rank-corr={summary['xgb_real_synth']['rank']}"
    )


if __name__ == "__main__":
    main()
