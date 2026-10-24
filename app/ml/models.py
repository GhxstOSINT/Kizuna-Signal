"""Baselines and the primary learner. Constrained on purpose: the first dataset is small."""
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from xgboost import XGBRegressor


class StateMeanBaseline:
    """Predicts each state's average share across training titles."""

    name = "state_mean"

    def __init__(self, target: str = "share"):
        self.target = target

    def fit(self, rows: pd.DataFrame, cols: list[str]):
        self.means_ = rows.groupby("state")[self.target].mean()
        self.global_ = rows[self.target].mean()
        return self

    def predict(self, rows: pd.DataFrame, cols: list[str]) -> np.ndarray:
        return rows["state"].map(self.means_).fillna(self.global_).to_numpy()


class RidgeModel:
    """Transparent benchmark: state effect plus genre x state interactions.

    Genre alone is constant across a title's states, so it cannot change the state
    ranking; the interaction terms let each genre lift or lower particular states.
    """

    name = "ridge_genre_state"

    def __init__(self, alpha: float = 5.0, target: str = "share"):
        self.alpha, self.target = alpha, target

    @staticmethod
    def _design(rows, cols) -> np.ndarray:
        title_cols = [c for c in cols if c.startswith(("genre_", "format_"))]
        state_cols = [c for c in cols if c.startswith("state_")]
        t, s = rows[title_cols].to_numpy(float), rows[state_cols].to_numpy(float)
        inter = (t[:, :, None] * s[:, None, :]).reshape(len(rows), -1)
        return np.hstack([s, inter])

    def fit(self, rows, cols):
        self.model_ = Ridge(alpha=self.alpha).fit(self._design(rows, cols), rows[self.target])
        return self

    def predict(self, rows, cols):
        return self.model_.predict(self._design(rows, cols))


class XGBModel:
    name = "xgboost"

    def __init__(self, target: str = "share", **params):
        self.target = target
        self.params = {"n_estimators": 200, "max_depth": 3, "learning_rate": 0.05,
                       "subsample": 0.8, "colsample_bytree": 0.8, "min_child_weight": 5,
                       "reg_lambda": 5.0, "random_state": 0, **params}

    def fit(self, rows, cols):
        self.model_ = XGBRegressor(**self.params).fit(rows[cols], rows[self.target])
        return self

    def predict(self, rows, cols):
        return self.model_.predict(rows[cols])


class EnsembleModel:
    """Weighted blend of the transparent baseline and XGBoost (architecture: Baseline + XGBoost)."""

    name = "ensemble"

    def __init__(self, members: list, weights: list[float] | None = None):
        self.members = members
        self.weights = weights or [1 / len(members)] * len(members)

    def fit_weights(self, rows: pd.DataFrame, cols: list[str]) -> "EnsembleModel":
        """Pick the blend weight on held-out calibration rows (minimum RMSE)."""
        a, b = (m.predict(rows, cols) for m in self.members[:2])
        grid = np.linspace(0, 1, 11)
        errs = [np.sqrt(np.mean((w * a + (1 - w) * b - rows["share"].to_numpy()) ** 2)) for w in grid]
        w = float(grid[int(np.argmin(errs))])
        self.weights = [w, 1 - w]
        return self

    def predict(self, rows, cols):
        return sum(w * m.predict(rows, cols) for w, m in zip(self.weights, self.members))
