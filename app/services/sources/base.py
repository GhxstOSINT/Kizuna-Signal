from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

from app.db.models import Title

# What parsing raises when a provider answers 200 with JSON that lacks the expected shape
# (a list instead of an object, a missing key, a string where a list belongs).
MALFORMED_RESPONSE_ERRORS = (KeyError, IndexError, TypeError, AttributeError)


@dataclass(slots=True)
class SourceEvidence:
    source: str
    status: Literal["available", "cached", "unavailable"]
    freshness_score: float
    quality_score: float
    metrics: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    provenance: dict[str, str] = field(default_factory=dict)
    # Per-state signals keyed by canonical state name (see app.services.census).
    regional: dict[str, dict[str, float]] = field(default_factory=dict)
    # Reference titles discovered by this source (AniList); consumed by find_comparables.
    comparables: list[dict] = field(default_factory=list)


class SourceAdapter(ABC):
    name: str

    @abstractmethod
    def collect(self, title: Title) -> SourceEvidence:
        raise NotImplementedError
