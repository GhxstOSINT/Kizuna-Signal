"""State-level demand model: feature encoding and stdlib-only inference.

Training (numpy) lives in regional_train.py; this module has no third-party imports so the
API can score without numpy.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.ml.census import BUDGETS, FORMATS, GENRES, PLATFORMS, STATES

ARTIFACT_PATH = Path(__file__).resolve().parent / "artifacts" / "regional_model.json"
MODEL_VERSION = "kizuna-census-ridge-1.0.0"

NS, NG, NF, NP, NB = len(STATES), len(GENRES), len(FORMATS), len(PLATFORMS), len(BUDGETS)
# Column offsets of the design matrix.
O_STATE = 1
O_GENRE = O_STATE + NS
O_FORMAT = O_GENRE + NG
O_PLATFORM = O_FORMAT + NF
O_BUDGET = O_PLATFORM + NP
O_SG = O_BUDGET + NB
O_SF = O_SG + NS * NG
O_SP = O_SF + NS * NF
O_SB = O_SP + NS * NP
O_LANG = O_SB + NS * NB
O_AGE = O_LANG + 1
N_FEATURES = O_AGE + 1

GENRE_ALIASES = {
    "mystery": "mystery_thriller",
    "thriller": "mystery_thriller",
    "psychological": "mystery_thriller",
    "sci-fi": "scifi",
    "sci fi": "scifi",
    "science fiction": "scifi",
    "adventure": "action",
    "coming of age": "drama",
    "slice of life": "drama",
    "horror": "supernatural",
    "soap opera": "family_drama",
    "family": "family_drama",
    "musical": "musical_romance",
    "bollywood": "musical_romance",
}
FORMAT_ALIASES = {
    "anime series": "series",
    "animated film": "film",
    "movie": "film",
    "serial": "soap_opera",
    "soap": "soap_opera",
    "special": "film",
}
PLATFORM_ALIASES = {"broadcast": "broadcast_tv", "tv": "broadcast_tv", "undecided": "ott"}


def _resolve(value: str, options: tuple[str, ...], aliases: dict[str, str], default: str) -> str:
    key = value.strip().lower().replace("-", " ") if value else ""
    key_us = key.replace(" ", "_")
    if key_us in options:
        return key_us
    if key in aliases:
        return aliases[key]
    return default


def resolve_genre(value: str) -> str:
    return _resolve(value, GENRES, GENRE_ALIASES, "drama")


def resolve_format(value: str) -> str:
    return _resolve(value, FORMATS, FORMAT_ALIASES, "series")


def resolve_platform(value: str) -> str:
    return _resolve(value, PLATFORMS, PLATFORM_ALIASES, "ott")


def resolve_budget(value: str) -> str:
    return _resolve(value, BUDGETS, {}, "medium")


def active_columns(state: int, genre: int, fmt: int, platform: int, budget: int) -> list[int]:
    """Indices of the 1.0-valued columns (the intercept is column 0)."""
    return [
        0,
        O_STATE + state,
        O_GENRE + genre,
        O_FORMAT + fmt,
        O_PLATFORM + platform,
        O_BUDGET + budget,
        O_SG + state * NG + genre,
        O_SF + state * NF + fmt,
        O_SP + state * NP + platform,
        O_SB + state * NB + budget,
    ]


_cache: dict | None = None


def load(path: Path = ARTIFACT_PATH) -> dict | None:
    global _cache
    if _cache is None and path.exists():
        _cache = json.loads(path.read_text(encoding="utf-8"))
    return _cache


def predict_states(
    genres: list[str],
    content_format: str,
    platform: str,
    budget: str,
    languages: list[str],
    age_years: float = 0.0,
    state_languages: dict[str, str] | None = None,
) -> dict[str, dict] | None:
    """Per-state demand (0-100) with an 80% conformal interval; None when no artifact exists.

    Multiple genres are averaged. `languages` are the title's localisation languages.
    """
    artifact = load()
    if artifact is None:
        return None
    w = artifact["coefficients"]
    age_mean, age_sd = artifact["normalisation"]["age"]
    lang_mean, lang_sd = artifact["normalisation"]["language_match"]
    half = artifact["conformal"]["q80"]
    resolved = [GENRES.index(resolve_genre(g)) for g in genres] or [GENRES.index("drama")]
    fmt = FORMATS.index(resolve_format(content_format))
    plat = PLATFORMS.index(resolve_platform(platform))
    bud = BUDGETS.index(resolve_budget(budget))
    wanted = {item.lower() for item in languages}
    age_z = (age_years - age_mean) / age_sd
    out: dict[str, dict] = {}
    for s, state in enumerate(STATES):
        match = 1.0 if (state_languages or {}).get(state, "").lower() in wanted else 0.0
        lang_z = (match - lang_mean) / lang_sd
        values = []
        for g in resolved:
            raw = sum(w[c] for c in active_columns(s, g, fmt, plat, bud))
            raw += w[O_LANG] * lang_z + w[O_AGE] * age_z
            values.append(raw)
        value = min(100.0, max(0.0, sum(values) / len(values)))
        out[state] = {
            "demand": round(value, 2),
            "interval_80": (round(max(0.0, value - half), 2), round(min(100.0, value + half), 2)),
        }
    return out
