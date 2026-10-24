from __future__ import annotations

import json
import math
import random
import statistics
from pathlib import Path

from app.ml.corpus import GENRES

ARTIFACT_PATH = Path(__file__).resolve().parent / "artifacts" / "market_model.json"
REFERENCE_YEAR = 2026
MIN_IMPROVEMENT_PCT = 15.0
FEATURE_NAMES = [*(f"genre_{g}" for g in GENRES), "is_film", "age"]


def featurize(genres: list[str], is_film: bool, year: int) -> list[float]:
    present = set(genres)
    return [
        *(1.0 if g in present else 0.0 for g in GENRES),
        1.0 if is_film else 0.0,
        (REFERENCE_YEAR - year) / 30,
    ]


def _row_features(row: dict) -> list[float]:
    return featurize(row["genres"], row["is_film"], row["year"])


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        m[col], m[pivot] = m[pivot], m[col]
        for r in range(col + 1, n):
            factor = m[r][col] / m[col][col]
            for c in range(col, n + 1):
                m[r][c] -= factor * m[col][c]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (m[i][n] - sum(m[i][j] * x[j] for j in range(i + 1, n))) / m[i][i]
    return x


def fit_ridge(
    x: list[list[float]], y: list[float], weights: list[float], lam: float
) -> tuple[float, list[float]]:
    """Weighted ridge regression with an unpenalised intercept (via weighted centering)."""
    total = sum(weights)
    d = len(x[0])
    x_mean = [sum(w * row[j] for w, row in zip(weights, x, strict=True)) / total for j in range(d)]
    y_mean = sum(w * v for w, v in zip(weights, y, strict=True)) / total
    xtx = [[0.0] * d for _ in range(d)]
    xty = [0.0] * d
    for w, row, target in zip(weights, x, y, strict=True):
        centered = [row[j] - x_mean[j] for j in range(d)]
        for i in range(d):
            xty[i] += w * centered[i] * (target - y_mean)
            for j in range(d):
                xtx[i][j] += w * centered[i] * centered[j]
    for i in range(d):
        xtx[i][i] += lam
    coef = _solve(xtx, xty)
    intercept = y_mean - sum(c * m for c, m in zip(coef, x_mean, strict=True))
    return intercept, coef


def predict_raw(intercept: float, coef: list[float], features: list[float]) -> float:
    return intercept + sum(c * f for c, f in zip(coef, features, strict=True))


class GaussianGenerator:
    """Parametric bootstrap fitted on real rows only.

    Genre/format flags ~ Bernoulli(empirical rate); release year ~ Normal(mean, sd), clipped to
    the observed range. Label = ridge prediction fitted on the real rows plus Normal(0, residual
    sd) noise, clipped to [0, 100]. Rows are synthetic by construction and never evaluated.
    """

    def __init__(self, rows: list[dict], lam: float, rng: random.Random):
        self.rng = rng
        x = [_row_features(r) for r in rows]
        y = [r["performance"] for r in rows]
        self.intercept, self.coef = fit_ridge(x, y, [1.0] * len(rows), lam)
        residuals = [
            t - predict_raw(self.intercept, self.coef, f) for t, f in zip(y, x, strict=True)
        ]
        self.sigma = statistics.pstdev(residuals) or 1.0
        n = len(rows)
        self.genre_rate = {g: sum(g in r["genres"] for r in rows) / n for g in GENRES}
        self.film_rate = sum(r["is_film"] for r in rows) / n
        years = [r["year"] for r in rows]
        self.year_mean, self.year_sd = statistics.mean(years), statistics.pstdev(years) or 1.0
        self.year_range = (min(years), max(years))

    def sample(self, n: int) -> list[dict]:
        out = []
        for _ in range(n):
            genres = [g for g in GENRES if self.rng.random() < self.genre_rate[g]] or [
                self.rng.choice(GENRES)
            ]
            is_film = self.rng.random() < self.film_rate
            year = round(
                min(
                    max(self.rng.gauss(self.year_mean, self.year_sd), self.year_range[0]),
                    self.year_range[1],
                )
            )
            mean = predict_raw(self.intercept, self.coef, featurize(genres, is_film, year))
            performance = min(100.0, max(0.0, self.rng.gauss(mean, self.sigma)))
            out.append(
                {
                    "genres": genres,
                    "is_film": is_film,
                    "year": year,
                    "performance": round(performance, 2),
                    "synthetic": True,
                }
            )
        return out


def _fit_with_synthetic(
    train_rows: list[dict], lam: float, synth_weight: float, n_synth: int, seed: int
) -> tuple[float, list[float]]:
    x = [_row_features(r) for r in train_rows]
    y = [r["performance"] for r in train_rows]
    w = [1.0] * len(train_rows)
    if synth_weight > 0:
        synth = GaussianGenerator(train_rows, lam, random.Random(seed)).sample(n_synth)
        x += [_row_features(r) for r in synth]
        y += [r["performance"] for r in synth]
        w += [synth_weight] * len(synth)
    return fit_ridge(x, y, w, lam)


def leave_one_out(
    rows: list[dict], lam: float, synth_weight: float, n_synth: int, seed: int
) -> tuple[list[float], list[float]]:
    """Synthetic data is regenerated from each training fold; only the held-out real row is scored."""
    errors, preds = [], []
    for i, held in enumerate(rows):
        b0, coef = _fit_with_synthetic(
            rows[:i] + rows[i + 1 :], lam, synth_weight, n_synth, seed + i
        )
        pred = min(100.0, max(0.0, predict_raw(b0, coef, _row_features(held))))
        preds.append(pred)
        errors.append(abs(pred - held["performance"]))
    return errors, preds


def r_squared(y: list[float], preds: list[float]) -> float:
    mean = statistics.mean(y)
    ss_tot = sum((v - mean) ** 2 for v in y)
    return 1 - sum((v - p) ** 2 for v, p in zip(y, preds, strict=True)) / ss_tot


def quantile(values: list[float], q: float) -> float:
    """Split-conformal rank: ceil(q * (n + 1))."""
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(q * (len(ordered) + 1)) - 1)]


def train(rows: list[dict], seed: int = 7, n_synth: int = 400) -> dict:
    y = [r["performance"] for r in rows]
    baseline_mae = statistics.mean(
        abs(v - statistics.mean(y[:i] + y[i + 1 :])) for i, v in enumerate(y)
    )

    grid = []
    for lam in (1.0, 3.0, 10.0, 30.0, 100.0):
        for synth_weight in (0.0, 0.05, 0.15, 0.3):
            errors, preds = leave_one_out(rows, lam, synth_weight, n_synth, seed)
            grid.append(
                {
                    "lambda": lam,
                    "synthetic_weight": synth_weight,
                    "loo_mae": round(statistics.mean(errors), 3),
                    "loo_r2": round(r_squared(y, preds), 3),
                }
            )
    best = min(grid, key=lambda g: g["loo_mae"])
    no_synth = min((g for g in grid if g["synthetic_weight"] == 0), key=lambda g: g["loo_mae"])

    errors, _ = leave_one_out(rows, best["lambda"], best["synthetic_weight"], n_synth, seed)
    intercept, coef = _fit_with_synthetic(
        rows, best["lambda"], best["synthetic_weight"], n_synth, seed
    )
    q80, q90 = quantile(errors, 0.8), quantile(errors, 0.9)
    return {
        "model": "weighted-ridge-regression",
        "target": "india_performance (0-100)",
        "seed": seed,
        "feature_names": FEATURE_NAMES,
        "intercept": intercept,
        "coefficients": coef,
        "hyperparameters": {
            "lambda": best["lambda"],
            "synthetic_weight": best["synthetic_weight"],
            "synthetic_rows": n_synth if best["synthetic_weight"] > 0 else 0,
        },
        "label_range": max(y) - min(y),
        "conformal": {"q80": round(q80, 3), "q90": round(q90, 3)},
        "metrics": {
            "real_rows": len(rows),
            "evaluation": "leave-one-out on real rows only; synthetic regenerated per fold",
            "baseline_mean_mae": round(baseline_mae, 3),
            "loo_mae": best["loo_mae"],
            "loo_r2": best["loo_r2"],
            "mae_improvement_vs_baseline_pct": round(100 * (1 - best["loo_mae"] / baseline_mae), 1),
            "best_without_synthetic": no_synth,
            "synthetic_helped": best["synthetic_weight"] > 0
            and best["loo_mae"] < no_synth["loo_mae"],
            "grid": grid,
        },
    }


def save(artifact: dict, path: Path = ARTIFACT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")


_cache: dict | None = None


def load(path: Path = ARTIFACT_PATH) -> dict | None:
    global _cache
    if _cache is None and path.exists():
        _cache = json.loads(path.read_text(encoding="utf-8"))
    return _cache


def predict(genres: list[str], is_film: bool, year: int) -> dict | None:
    """Predicted India performance, conformal 80% interval, and a 0-100 confidence.

    confidence = 100 * (1 - interval_half_width / label_range): 100 means a zero-width interval.
    """
    artifact = load()
    if artifact is None:
        return None
    value = predict_raw(
        artifact["intercept"], artifact["coefficients"], featurize(genres, is_film, year)
    )
    value = min(100.0, max(0.0, value))
    half = artifact["conformal"]["q80"]
    metrics = artifact["metrics"]
    return {
        # Only trust the model when it beats the mean-predictor baseline by a clear margin.
        "usable": metrics["mae_improvement_vs_baseline_pct"] >= MIN_IMPROVEMENT_PCT
        and metrics["loo_r2"] > 0.1,
        "prediction": round(value, 2),
        "interval_80": (round(max(0, value - half), 2), round(min(100, value + half), 2)),
        "confidence": round(100 * max(0.0, 1 - half / artifact["label_range"]), 1),
    }
