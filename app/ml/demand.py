"""Turn Trends time series into pre-release demand features and post-release state labels.

Windows are anchored on the title's release date:
  pre        release-12w .. release      -> FEATURES (knowable before launch)
  launch     release .. release+8w       -> LABEL
  sustained  release+8w .. release+52w   -> LABEL
Post-release data never becomes a feature.
"""
from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.adapters.google_trends import TrendsClient, TrendsError
from app.ml.schema import TitleRecord

PRE_WEEKS, LAUNCH_WEEKS, TOTAL_POST_WEEKS = 12, 8, 52
MIN_POST_SUM = 5  # below this a state has too little signal (Trends rounds small values to 0)
MIN_VALID_STATES = 6


def search_term(title: TitleRecord) -> tuple[str, str] | None:
    """Query text and which title variant was used (query variants are tracked)."""
    for variant, name in (("english", title.english_title), ("romanized", title.romanized_title)):
        if name:
            name = name.split(":")[0].strip()[:60]
            return (f"{name} anime" if len(name.split()) <= 2 else name), variant
    return None


def window_bounds(release: date) -> tuple[date, date]:
    return release - timedelta(weeks=PRE_WEEKS), release + timedelta(weeks=TOTAL_POST_WEEKS)


def is_eligible(title: TitleRecord, today: date) -> bool:
    release = title.anchor_date()
    return release is not None and window_bounds(release)[1] <= today - timedelta(days=14)


def _split(rows: list[dict], term: str, anchor: str, release: date):
    df = pd.DataFrame([{"date": date.fromisoformat(r["date"]), "t": r["values"][term],
                        "a": r["values"][anchor], "partial": r["partial"]} for r in rows])
    if df.empty:
        return df, df, df
    df = df[~df["partial"]]
    pre = df[df["date"] < release]
    launch = df[(df["date"] >= release) & (df["date"] < release + timedelta(weeks=LAUNCH_WEEKS))]
    post = df[df["date"] >= release]
    return pre, launch, post


def _ratio(frame: pd.DataFrame) -> float:
    return float(frame["t"].sum() / max(frame["a"].sum(), 1)) if len(frame) else 0.0


def summarize_state(rows: list[dict], term: str, anchor: str, release: date) -> dict | None:
    """Pre-release features and post-release ratio for one (title, state). None if no usable signal."""
    pre, launch, post = _split(rows, term, anchor, release)
    if len(post) == 0 or post["t"].sum() < MIN_POST_SUM:
        return None
    pre_vals = pre["t"].to_numpy(dtype=float)
    slope = float(np.polyfit(np.arange(len(pre_vals)), pre_vals, 1)[0]) if len(pre_vals) >= 3 else 0.0
    mean = float(pre_vals.mean()) if len(pre_vals) else 0.0
    return {
        "pre_has_data": int(pre["t"].sum() > 0),
        "pre_level": _ratio(pre),
        "pre_growth": slope,
        "pre_volatility": float(pre_vals.std() / (mean + 1.0)) if len(pre_vals) else 0.0,
        "post_ratio": _ratio(post),
        "launch_ratio": _ratio(launch),
    }


def collect_title(client: TrendsClient, title: TitleRecord, states: list[str]):
    """Returns (demand_rows, label_rows, report) for one title; ([], [], report) if unusable."""
    query = search_term(title)
    release = title.anchor_date()
    report = {"title_id": title.title_id, "query": query, "states_ok": 0, "from_cache": 0, "error": None}
    if query is None or release is None:
        report["error"] = "no_query_or_release_date"
        return [], [], report
    term, _ = query
    start, end = window_bounds(release)
    per_state = {}
    for geo in states:
        try:
            env = client.fetch(term, geo, start, end)
        except TrendsError as exc:
            report["error"] = str(exc)
            break
        report["from_cache"] += env["from_cache"]
        summary = summarize_state(env["rows"], term, env["terms"][1], release)
        if summary:
            per_state[geo] = summary
    report["states_ok"] = len(per_state)
    if len(per_state) < MIN_VALID_STATES:
        report["error"] = report["error"] or "too_few_states_with_signal"
        return [], [], report
    total = sum(s["post_ratio"] for s in per_state.values()) or 1.0
    demand = [{"title_id": title.title_id, "state": g,
               **{k: v for k, v in s.items() if k.startswith("pre_")}} for g, s in per_state.items()]
    labels = [{"title_id": title.title_id, "state": g, "share": s["post_ratio"] / total}
              for g, s in per_state.items()]
    return demand, labels, report
