"""State-level signals: CSV import, canonical state names, per-capita normalisation, indexing.

Rows are stored in `state_signals` with their source and the date they describe. Volume metrics
(views, watch hours...) are divided by Census 2011 state population before comparison, so large
states do not win just by being large; rate metrics are compared as given.
"""

from __future__ import annotations

import csv
import io
import math
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import StateSignal
from app.ml.census import CENSUS, STATES
from app.ml.levenshtein import name_similarity

VOLUME_METRICS = {"views", "watch_hours", "streams", "viewers", "subscribers"}
RATE_METRICS = {"index", "share_of_state_pct", "penetration_pct", "completion_rate_pct"}
ALLOWED_METRICS = VOLUME_METRICS | RATE_METRICS
STATE_ALIASES = {
    "delhi": "Delhi NCR", "new delhi": "Delhi NCR", "nct of delhi": "Delhi NCR", "ncr": "Delhi NCR",
    "up": "Uttar Pradesh", "tn": "Tamil Nadu", "mh": "Maharashtra", "wb": "West Bengal",
    "ka": "Karnataka", "kl": "Kerala", "ts": "Telangana", "telengana": "Telangana",
}
MAX_ROWS = 5000
MAX_BYTES = 1_000_000
MIN_STATES_FOR_INDEX = 3
AUTOMATED_SOURCES = {"google_trends"}


@dataclass(slots=True)
class ParsedRow:
    state: str
    metric: str
    value: float
    as_of: date
    source: str


def canonical_state(raw: str) -> str | None:
    text = " ".join(raw.strip().lower().split())
    if text in STATE_ALIASES:
        return STATE_ALIASES[text]
    best = max(STATES, key=lambda s: name_similarity(text, s))
    return best if name_similarity(text, best) >= 0.85 else None


def parse_csv(text: str, default_source: str) -> tuple[list[ParsedRow], list[dict]]:
    """Validate a state-signal CSV. Columns: state, metric, value, [as_of YYYY-MM-DD], [source]."""
    reader = csv.DictReader(io.StringIO(text))
    fields = {(name or "").strip().lower() for name in reader.fieldnames or []}
    missing = {"state", "metric", "value"} - fields
    if missing:
        raise ValueError(f"CSV is missing required column(s): {', '.join(sorted(missing))}")
    rows: list[ParsedRow] = []
    rejected: list[dict] = []
    for number, raw in enumerate(reader, start=2):
        if number - 1 > MAX_ROWS:
            raise ValueError(f"CSV has more than {MAX_ROWS} rows")
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        state = canonical_state(row["state"])
        metric = row["metric"].lower().replace(" ", "_")
        reason = None
        try:
            value = float(row["value"])
            as_of = date.fromisoformat(row["as_of"]) if row.get("as_of") else date.today()
        except ValueError:
            value, as_of = math.nan, date.today()
            reason = "value must be a number and as_of must be YYYY-MM-DD"
        if reason is None:
            if state is None:
                reason = f"unknown state '{row['state']}'"
            elif metric not in ALLOWED_METRICS:
                reason = (
                    f"unknown metric '{row['metric']}' (allowed: {', '.join(sorted(ALLOWED_METRICS))})"
                )
            elif not math.isfinite(value) or value < 0:
                reason = "value must be a finite number >= 0"
            elif as_of > date.today():
                reason = "as_of is in the future"
        if reason:
            rejected.append({"row": number, "reason": reason})
            continue
        rows.append(ParsedRow(state, metric, value, as_of, row.get("source") or default_source))
    return rows, rejected


def store_rows(db: Session, title_id: str, rows: list[ParsedRow], detail: dict | None = None) -> str:
    batch = str(uuid.uuid4())
    for row in rows:
        db.add(
            StateSignal(
                title_id=title_id, state=row.state, source=row.source, metric=row.metric,
                value=row.value, as_of=row.as_of, detail=detail or {}, import_batch=batch,
            )
        )
    db.commit()
    return batch


def replace_source_for_day(
    db: Session, title_id: str, source: str, rows: list[ParsedRow], detail: dict | None = None
) -> None:
    """Idempotent store for automated sources: one snapshot per title, source and day."""
    db.execute(
        delete(StateSignal).where(
            StateSignal.title_id == title_id,
            StateSignal.source == source,
            StateSignal.as_of == date.today(),
        )
    )
    for row in rows:
        db.add(
            StateSignal(
                title_id=title_id, state=row.state, source=source, metric=row.metric,
                value=row.value, as_of=row.as_of, detail=detail or {},
            )
        )
    db.commit()


def _series_index(rows: list[StateSignal]) -> dict[str, float] | None:
    """0-100 index (top state = 100) for one (source, metric) series, latest date only."""
    latest = max(r.as_of for r in rows)
    per_state: dict[str, list[float]] = {}
    for r in rows:
        if r.as_of == latest:
            per_state.setdefault(r.state, []).append(r.value)
    if len(per_state) < MIN_STATES_FOR_INDEX:
        return None
    metric = rows[0].metric
    values = {}
    for state, vals in per_state.items():
        if metric in VOLUME_METRICS:
            values[state] = sum(vals) / CENSUS[state]["population_m"]
        else:
            values[state] = sum(vals) / len(vals)
    top = max(values.values())
    return {s: 100 * v / top for s, v in values.items()} if top > 0 else None


def load_partner_index(db: Session, title_id: str) -> dict[str, float] | None:
    """Average of the per-series indices from imported (non-automated) sources."""
    rows = list(
        db.scalars(
            select(StateSignal).where(
                StateSignal.title_id == title_id, StateSignal.source.not_in(AUTOMATED_SOURCES)
            )
        )
    )
    series: dict[tuple[str, str], list[StateSignal]] = {}
    for row in rows:
        series.setdefault((row.source, row.metric), []).append(row)
    indices = [idx for idx in (_series_index(r) for r in series.values()) if idx]
    if not indices:
        return None
    out: dict[str, float] = {}
    for state in STATES:
        present = [idx[state] for idx in indices if state in idx]
        if present:
            out[state] = round(sum(present) / len(present), 2)
    return out or None
