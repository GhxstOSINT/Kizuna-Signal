"""Split-conformal prediction intervals: distribution-free, calibrated on held-out titles."""

import math

import numpy as np


class ConformalInterval:
    def __init__(self, alpha: float = 0.2, floor_at_zero: bool = True):
        self.alpha = alpha  # 0.2 -> nominal 80% coverage
        self.floor_at_zero = floor_at_zero  # shares cannot be negative; log-scale lift can

    def fit(self, y_true: np.ndarray, y_pred: np.ndarray) -> "ConformalInterval":
        residuals = np.sort(np.abs(np.asarray(y_true) - np.asarray(y_pred)))
        n = len(residuals)
        rank = min(n, math.ceil((n + 1) * (1 - self.alpha)))
        self.q_ = float(residuals[rank - 1])
        return self

    def predict(self, y_pred: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return (
            np.clip(y_pred - self.q_, 0, None) if self.floor_at_zero else y_pred - self.q_
        ), y_pred + self.q_

    def coverage(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        lo, hi = self.predict(y_pred)
        return float(np.mean((y_true >= lo) & (y_true <= hi)))
