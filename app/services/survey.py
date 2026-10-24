from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.services.census import resolve_state
from app.services.textmatch import normalise

logger = logging.getLogger(__name__)

NATIONAL = {"india", "all india", "national", "all"}
REQUIRED_COLUMNS = {"state", "genre", "index"}
STALE_AFTER_YEARS = 3


@dataclass(frozen=True, slots=True)
class SurveyRow:
    state: str | None  # canonical Census state name, or None for national rows
    genre: str
    content_type: str
    index: float
    sample_size: float
    year: int | None
    source: str


@dataclass(slots=True)
class Affinity:
    index: float  # weighted mean; 100 = that state's average viewer
    sample_size: float
    rows: int
    years: tuple[int, int] | None
    sources: tuple[str, ...]

    @property
    def score(self) -> float:
        """Map the index onto 0-100: 100 -> 50 (average), 200 -> 100, 0 -> 0."""
        return round(max(0.0, min(100.0, 50 + (self.index - 100) * 0.5)), 2)


class SurveyData:
    """Survey / viewing-behaviour rows loaded from CSV files (schema: data/survey/README.md).

    One row says how strongly viewers in a state over- or under-index on a genre (and optionally a
    content type) relative to that state's average viewer: index 100 = average, 150 = 50% more.
    """

    def __init__(self, rows: list[SurveyRow] | None = None, errors: list[str] | None = None):
        self.rows = rows or []
        self.errors = errors or []

    @property
    def empty(self) -> bool:
        return not self.rows

    @classmethod
    def from_dir(cls, directory: str | Path) -> SurveyData:
        folder = Path(directory)
        rows: list[SurveyRow] = []
        errors: list[str] = []
        if not folder.is_dir():
            return cls()
        for path in sorted(folder.glob("*.csv")):
            file_rows, file_errors = cls._read(path)
            rows.extend(file_rows)
            errors.extend(file_errors)
        return cls(rows, errors)

    @staticmethod
    def _read(path: Path) -> tuple[list[SurveyRow], list[str]]:
        rows: list[SurveyRow] = []
        errors: list[str] = []
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(line for line in handle if not line.startswith("#"))
            header = {(name or "").strip().casefold() for name in reader.fieldnames or []}
            missing = REQUIRED_COLUMNS - header
            if missing:
                return [], [
                    f"{path.name}: missing required column(s): {', '.join(sorted(missing))}"
                ]
            for line_no, raw in enumerate(reader, start=2):
                row = {(k or "").strip().casefold(): (v or "").strip() for k, v in raw.items()}
                where = f"{path.name}:{line_no}"
                state_text = row["state"]
                state = None
                if normalise(state_text) not in NATIONAL:
                    resolved = resolve_state(state_text)
                    if resolved is None:
                        errors.append(f"{where}: unknown state '{state_text}'")
                        continue
                    state = resolved.name
                try:
                    index = float(row["index"])
                    sample = float(row.get("sample_size") or 1)
                    year = int(row["year"]) if row.get("year") else None
                except ValueError:
                    errors.append(f"{where}: index/sample_size/year must be numeric")
                    continue
                if not row["genre"] or index < 0 or sample <= 0:
                    errors.append(f"{where}: genre required, index >= 0, sample_size > 0")
                    continue
                rows.append(
                    SurveyRow(
                        state=state,
                        genre=normalise(row["genre"]),
                        content_type=normalise(row.get("content_type", "")),
                        index=index,
                        sample_size=sample,
                        year=year,
                        source=row.get("source") or path.name,
                    )
                )
        return rows, errors

    def affinity(
        self, state: str | None, genres: set[str], content_format: str = ""
    ) -> Affinity | None:
        """Weighted genre/content-type affinity for a state (None = national rows)."""
        wanted = {normalise(g) for g in genres}
        fmt = normalise(content_format)
        matches = [
            row
            for row in self.rows
            if row.state == state
            and row.genre in wanted
            and (
                not row.content_type
                or not fmt
                or row.content_type in fmt
                or fmt in row.content_type
            )
        ]
        if not matches:
            return None
        weight = sum(row.sample_size for row in matches)
        years = [row.year for row in matches if row.year]
        return Affinity(
            index=sum(row.index * row.sample_size for row in matches) / weight,
            sample_size=weight,
            rows=len(matches),
            years=(min(years), max(years)) if years else None,
            sources=tuple(sorted({row.source for row in matches})),
        )

    def stale_warning(self, now: datetime | None = None) -> str | None:
        years = [row.year for row in self.rows if row.year]
        current = (now or datetime.now(UTC)).year
        notes = []
        if years and current - max(years) > STALE_AFTER_YEARS:
            notes.append(
                f"Survey data is from {max(years)} or earlier and may not reflect current viewing."
            )
        undated = len(self.rows) - len(years)
        if undated:
            notes.append(
                f"{undated} of {len(self.rows)} survey rows have no year, so their age cannot be "
                "checked."
            )
        return " ".join(notes) or None
