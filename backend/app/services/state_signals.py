"""State-level signals: CSV import, canonical state names, per-capita normalisation, indexing.

Rows are stored in `state_signals` with their source and the date they describe. Volume metrics
(views, watch hours...) are divided by Census population before comparison, so large states do
not win just by being large; rate metrics are compared as given. The index (top state = 100)
tilts the regional scores of an analysis (see `apply_partner_tilt`).
"""

from __future__ import annotations

import csv
import io
import math
import statistics
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import StateSignal
from app.schemas.analysis import RegionalScore
from app.services import census
from app.services.levenshtein import name_similarity

VOLUME_METRICS = {"views", "watch_hours", "streams", "viewers", "subscribers"}
RATE_METRICS = {"index", "share_of_state_pct", "penetration_pct", "completion_rate_pct"}
ALLOWED_METRICS = VOLUME_METRICS | RATE_METRICS
STATE_ABBREVIATIONS = {
    "up": "Uttar Pradesh",
    "tn": "Tamil Nadu",
    "mh": "Maharashtra",
    "wb": "West Bengal",
    "ka": "Karnataka",
    "kl": "Kerala",
    "ts": "Telangana",
    "ncr": "Delhi",
    "dl": "Delhi",
}
MAX_ROWS = 5000
MAX_BYTES = 1_000_000
MIN_STATES_FOR_INDEX = 3
AUTOMATED_SOURCES = {"google_trends"}
MAX_TILT = 8.0  # points; measured viewing outweighs the +/-5 a Trends reading could add
TILT_PER_INDEX_POINT = 0.3


@dataclass(slots=True)
class ParsedRow:
    state: str
    metric: str
    value: float
    as_of: date
    source: str


def canonical_state(raw: str) -> str | None:
    """Census name for a state/UT: exact or alias match, abbreviation, then close spelling."""
    profile = census.resolve_state(raw)
    if profile:
        return profile.name
    text = " ".join(raw.strip().lower().split())
    if text in STATE_ABBREVIATIONS:
        profile = census.resolve_state(STATE_ABBREVIATIONS[text])
        return profile.name if profile else None
    names = list(census.all_states())
    best = max(names, key=lambda name: name_similarity(text, name))
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
                    f"unknown metric '{row['metric']}' "
                    f"(allowed: {', '.join(sorted(ALLOWED_METRICS))})"
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


def store_rows(
    db: Session, title_id: str, rows: list[ParsedRow], detail: dict | None = None
) -> str:
    batch = str(uuid.uuid4())
    for row in rows:
        db.add(
            StateSignal(
                title_id=title_id,
                state=row.state,
                source=row.source,
                metric=row.metric,
                value=row.value,
                as_of=row.as_of,
                detail=detail or {},
                import_batch=batch,
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
                title_id=title_id,
                state=row.state,
                source=source,
                metric=row.metric,
                value=row.value,
                as_of=row.as_of,
                detail=detail or {},
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
    states = census.all_states()
    values: dict[str, float] = {}
    for state, vals in per_state.items():
        if metric in VOLUME_METRICS:
            population = states[state].population if state in states else None
            if not population:
                continue
            values[state] = sum(vals) / population
        else:
            values[state] = sum(vals) / len(vals)
    if len(values) < MIN_STATES_FOR_INDEX:
        return None
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
    for state in census.all_states():
        present = [idx[state] for idx in indices if state in idx]
        if present:
            out[state] = round(sum(present) / len(present), 2)
    return out or None


def partner_tilt(index: dict[str, float] | None) -> dict[str, float] | None:
    """Index as points above/below the mean of the states that have data (capped at +/-8)."""
    if not index or len(index) < MIN_STATES_FOR_INDEX:
        return None
    mean = statistics.mean(index.values())
    return {
        state: max(-MAX_TILT, min(MAX_TILT, TILT_PER_INDEX_POINT * (value - mean)))
        for state, value in index.items()
    }


def apply_partner_tilt(
    regions: list[RegionalScore], index: dict[str, float] | None
) -> list[RegionalScore]:
    """Shift each state's score by its imported-viewing tilt and explain it. Re-sorts by score."""
    tilt = partner_tilt(index)
    if not tilt:
        return regions
    out = []
    for region in regions:
        if region.state in tilt and index is not None:
            shift = tilt[region.state]
            region = region.model_copy(
                update={
                    "score": round(max(0.0, min(100.0, region.score + shift)), 2),
                    "reasons": [
                        *region.reasons,
                        f"Imported viewing data (per-capita index {index[region.state]:.0f}/100) "
                        f"shifts this market by {shift:+.1f} points.",
                    ],
                }
            )
        out.append(region)
    return sorted(out, key=lambda r: r.score, reverse=True)


def trends_rows(regional: dict[str, dict[str, float]]) -> list[ParsedRow]:
    """Google Trends state interest from a SourceEvidence.regional mapping, as storable rows."""
    return [
        ParsedRow(state, "index", float(values["interest"]), date.today(), "google_trends")
        for state, values in regional.items()
        if "interest" in values
    ]
