from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

from app.db.models import Title


@dataclass(slots=True)
class SourceEvidence:
    source: str
    status: Literal["available", "cached", "unavailable"]
    freshness_score: float
    quality_score: float
    metrics: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    provenance: dict[str, str] = field(default_factory=dict)


class SourceAdapter(ABC):
    name: str

    @abstractmethod
    def collect(self, title: Title) -> SourceEvidence:
        raise NotImplementedError
