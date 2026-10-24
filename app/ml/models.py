"""Baselines and the primary learner. Constrained on purpose: the first dataset is small."""
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from xgboost import XGBRegressor


class StateMeanBaseline:
    """Predicts each state's average share across training titles."""

    name = "state_mean"

    def fit(self, rows: pd.DataFrame, cols: list[str]):
        self.means_ = rows.groupby("state")["share"].mean()
        self.global_ = rows["share"].mean()
        return self

    def predict(self, rows: pd.DataFrame, cols: list[str]) -> np.ndarray:
        return rows["state"].map(self.means_).fillna(self.global_).to_numpy()


class RidgeModel:
    """Transparent benchmark on genre/format/state features (no embeddings)."""

    name = "ridge_genre_state"

    def __init__(self, alpha: float = 5.0):
        self.alpha = alpha

    @staticmethod
    def _cols(cols):
        return [c for c in cols if c.startswith(("genre_", "format_", "state_"))]

    def fit(self, rows, cols):
        self.model_ = Ridge(alpha=self.alpha).fit(rows[self._cols(cols)], rows["share"])
        return self

    def predict(self, rows, cols):
        return self.model_.predict(rows[self._cols(cols)])


class XGBModel:
    name = "xgboost"

    def __init__(self, **params):
        self.params = {"n_estimators": 200, "max_depth": 3, "learning_rate": 0.05,
                       "subsample": 0.8, "colsample_bytree": 0.8, "min_child_weight": 5,
                       "reg_lambda": 5.0, "random_state": 0, **params}

    def fit(self, rows, cols):
        self.model_ = XGBRegressor(**self.params).fit(rows[cols], rows["share"])
        return self

    def predict(self, rows, cols):
        return self.model_.predict(rows[cols])
