"""State demographics and genre-affinity priors used to build the synthetic market dataset.

Population, urbanisation and literacy are approximate Census of India 2011 figures. The census
does NOT record media or genre preferences, so GENRE_AFFINITY and FORMAT_AFFINITY below are
documented modelling assumptions (editable priors), not census measurements.
"""

from __future__ import annotations

import json
from pathlib import Path

STATES = (
    "Maharashtra",
    "Karnataka",
    "Delhi NCR",
    "Tamil Nadu",
    "Telangana",
    "West Bengal",
    "Kerala",
    "Uttar Pradesh",
)
GENRES = (
    "action",
    "fantasy",
    "supernatural",
    "romance",
    "comedy",
    "drama",
    "mystery_thriller",
    "scifi",
    "sports",
    "family_drama",  # soap-opera style serials
    "musical_romance",  # Bollywood-style
)
FORMATS = ("film", "series", "soap_opera")
PLATFORMS = ("ott", "theatrical", "broadcast_tv")
BUDGETS = ("low", "medium", "high")

CENSUS_FILE = Path(__file__).resolve().parents[2] / "data" / "real" / "census_2011_states.json"


def _load_census() -> tuple[dict[str, dict[str, float]], dict]:
    """State figures from data/real/census_2011_states.json (population in millions, urban %,
    literacy %, plus optional household TV/internet shares once imported from the official tables)."""
    raw = json.loads(CENSUS_FILE.read_text(encoding="utf-8"))
    return raw["states"], {k: v for k, v in raw.items() if k != "states"}


CENSUS, CENSUS_META = _load_census()
CENSUS_VERIFIED = CENSUS_META.get("status") in {"verified", "secondary-verified"}


def reach_index(state: str) -> float:
    """Reach of a state relative to the best state (0-1): the average of urban x literacy and the
    share of households owning a TV, each scaled by the top state (Census 2011)."""
    urban_literacy = {s: CENSUS[s]["urban_pct"] * CENSUS[s]["literacy_pct"] for s in CENSUS}
    tv = {s: CENSUS[s]["tv_household_pct"] for s in CENSUS}
    return 0.5 * urban_literacy[state] / max(urban_literacy.values()) + 0.5 * tv[state] / max(tv.values())
TOP_STATE_COUNT = 4  # largest by population: Uttar Pradesh, Maharashtra, West Bengal, Tamil Nadu
TOP_STATE_INFLATION = 1.25  # multiplier on genre/format affinity in the top states

# Assumed genre affinity in score points, per state (default 0). Bollywood-style musical
# romance and family-drama/soap content over-index in the Hindi belt, Bengal and Tamil Nadu;
# action over-indexes in the Telugu/Tamil/Kannada markets; mystery and drama in Bengal/Kerala.
GENRE_AFFINITY: dict[str, dict[str, float]] = {
    "Uttar Pradesh": {"musical_romance": 8, "family_drama": 7, "action": 5, "comedy": 3, "drama": 2, "scifi": -4, "fantasy": -2},
    "Maharashtra": {"musical_romance": 7, "comedy": 4, "action": 4, "family_drama": 3, "romance": 3, "sports": 3},
    "Delhi NCR": {"mystery_thriller": 4, "scifi": 3, "action": 3, "musical_romance": 4, "romance": 2},
    "Tamil Nadu": {"family_drama": 8, "action": 6, "romance": 3, "fantasy": 3, "musical_romance": 2},
    "Telangana": {"action": 8, "fantasy": 4, "musical_romance": 3, "family_drama": 3, "supernatural": 2},
    "Karnataka": {"action": 5, "fantasy": 4, "scifi": 4, "supernatural": 3, "family_drama": 3},
    "West Bengal": {"family_drama": 7, "drama": 5, "mystery_thriller": 6, "musical_romance": 2, "romance": 2},
    "Kerala": {"drama": 6, "mystery_thriller": 6, "family_drama": 4, "comedy": 3, "scifi": 2},
}
# Assumed per-state score offset by format (soap operas/serials are strongest in the South,
# Bengal and the Hindi belt; theatrical films in Maharashtra and the Telugu market).
FORMAT_AFFINITY: dict[str, dict[str, float]] = {
    "Uttar Pradesh": {"soap_opera": 6, "film": 3},
    "Maharashtra": {"film": 5, "soap_opera": 2},
    "Delhi NCR": {"series": 4, "film": 2},
    "Tamil Nadu": {"soap_opera": 6, "film": 4},
    "Telangana": {"film": 6, "series": 1},
    "Karnataka": {"series": 3, "film": 2},
    "West Bengal": {"soap_opera": 6, "series": 1},
    "Kerala": {"soap_opera": 4, "film": 3},
}

# Global per-genre effect, shrunk toward zero from the 27 labelled real titles' mean India
# performance (see app/ml/corpus.py); keeps the synthetic data anchored to observed data.
PLATFORM_EFFECT = {"ott": 0.0, "theatrical": 1.0, "broadcast_tv": -1.0}
BUDGET_EFFECT = {"low": -4.0, "medium": 0.0, "high": 4.0}

TARGET_MEAN, TARGET_SD = 72.0, 9.0  # normalised onto the legacy 0-100 regional score scale


def top_states() -> set[str]:
    ranked = sorted(STATES, key=lambda s: CENSUS[s]["population_m"], reverse=True)
    return set(ranked[:TOP_STATE_COUNT])


def inflation(state: str) -> float:
    return TOP_STATE_INFLATION if state in top_states() else 1.0


def population_weights() -> list[float]:
    total = sum(CENSUS[s]["population_m"] for s in STATES)
    return [CENSUS[s]["population_m"] / total for s in STATES]
