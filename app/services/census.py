from __future__ import annotations

import csv
import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "india_states_census2011.csv"
CENSUS_YEAR = 2011


@dataclass(frozen=True, slots=True)
class StateProfile:
    name: str
    population: int
    urban_pct: float
    language: str


def _key(name: str) -> str:
    return re.sub(r"\s+", " ", name.casefold().replace("&", " and ")).strip()


@lru_cache
def _load() -> tuple[dict[str, StateProfile], dict[str, str]]:
    states: dict[str, StateProfile] = {}
    lookup: dict[str, str] = {}
    with DATA_FILE.open(encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(line for line in handle if not line.startswith("#"))
        for row in rows:
            profile = StateProfile(
                name=row["state"],
                population=int(row["population"]),
                urban_pct=float(row["urban_pct"]),
                language=row["language"],
            )
            states[profile.name] = profile
            lookup[_key(profile.name)] = profile.name
            for alias in filter(None, row["aliases"].split("|")):
                lookup[_key(alias)] = profile.name
    return states, lookup


def all_states() -> dict[str, StateProfile]:
    return dict(_load()[0])


def resolve_state(name: str) -> StateProfile | None:
    """Match a state/UT by canonical name or alias (e.g. 'Delhi NCR', 'Orissa')."""
    states, lookup = _load()
    canonical = lookup.get(_key(name))
    return states[canonical] if canonical else None


def total_population() -> int:
    return sum(state.population for state in _load()[0].values())


def states_for_languages(languages: Iterable[str]) -> list[StateProfile]:
    wanted = {_key(language) for language in languages}
    return [state for state in _load()[0].values() if _key(state.language) in wanted]


def population_share(states: Iterable[StateProfile], urban_weighted: bool = False) -> float:
    """Share of India's population (optionally its urban population) living in `states`."""
    everyone = _load()[0].values()

    def weight(state: StateProfile) -> float:
        return state.population * (state.urban_pct / 100 if urban_weighted else 1.0)

    total = sum(weight(state) for state in everyone)
    return sum(weight(state) for state in {s.name: s for s in states}.values()) / total
