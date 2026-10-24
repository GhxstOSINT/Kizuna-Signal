"""Local and global explanations using exact tree SHAP values from XGBoost (pred_contribs)."""
import pandas as pd
import xgboost as xgb

from app.ml.features import GROUP_PREFIXES


def contributions(model, rows: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """SHAP value per row and feature (the bias term is dropped)."""
    booster = model.model_.get_booster()
    values = booster.predict(xgb.DMatrix(rows[cols], feature_names=cols), pred_contribs=True)
    return pd.DataFrame(values[:, :-1], columns=cols, index=rows.index)


def local(contrib: pd.DataFrame, row_index, top: int = 5) -> list[dict]:
    r = contrib.loc[row_index]
    return [{"feature": f, "contribution": float(r[f])} for f in r.abs().nlargest(top).index]


def global_by_group(contrib: pd.DataFrame) -> dict[str, float]:
    """Mean |SHAP| share per feature group: how much each model component matters."""
    mean_abs = contrib.abs().mean()
    total = float(mean_abs.sum()) or 1.0
    out = {}
    for group, prefixes in GROUP_PREFIXES.items():
        out[group] = float(mean_abs[[c for c in contrib.columns if c.startswith(prefixes)]].sum() / total)
    return out
