from __future__ import annotations

import hashlib
import math

from app.db.models import Title
from app.services.sources.base import SourceAdapter, SourceEvidence
from app.services.sources.live import RegionalContextCensus


def stable_number(seed: str, low: float, high: float) -> float:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    ratio = int(digest[:12], 16) / float(16**12 - 1)
    return round(low + (high - low) * ratio, 4)


class DemoAdapter(SourceAdapter):
    def __init__(self, name: str, status: str = "available"):
        self.name = name
        self.forced_status = status

    def collect(self, title: Title) -> SourceEvidence:
        if self.forced_status == "unavailable":
            return SourceEvidence(
                source=self.name,
                status="unavailable",
                freshness_score=0.0,
                quality_score=0.0,
                warnings=[f"{self.name} is unavailable; analysis continued without this source."],
                provenance={"mode": "offline-demo", "title": title.name},
            )

        seed = f"{title.name}|{title.primary_genre}|{self.name}"
        base = stable_number(seed, 0.48, 0.88)
        genre_boost = (
            0.05
            if title.primary_genre.lower() in {"action", "fantasy", "romance", "thriller", "comedy"}
            else 0.0
        )
        franchise_boost = (
            0.04
            if (title.franchise_status or "").lower() not in {"", "original", "standalone"}
            else 0.0
        )
        value = min(0.95, base + genre_boost + franchise_boost)

        metrics_by_source = {
            "google_trends": {
                "relative_interest": value * 100,
                "momentum": stable_number(seed + "momentum", 0.35, 0.9) * 100,
                "stability": stable_number(seed + "stability", 0.45, 0.92) * 100,
            },
            "youtube": {
                "attention": value * 100,
                "engagement_quality": stable_number(seed + "engagement", 0.4, 0.88) * 100,
                "velocity": stable_number(seed + "velocity", 0.3, 0.9) * 100,
            },
            "wikimedia": {
                "curiosity": value * 100,
                "sustained_interest": stable_number(seed + "sustained", 0.42, 0.86) * 100,
            },
            "anilist": {
                "metadata_completeness": 92.0,
                "historical_affinity": value * 100,
            },
            "regional_context": {
                "language_fit": value * 100,
                "addressable_market": stable_number(seed + "market", 0.55, 0.92) * 100,
            },
        }
        status = "cached" if self.name == "google_trends" else "available"
        warnings = []
        if self.name == "google_trends":
            warnings.append(
                "Google Trends values are normalized relative interest, not absolute volume."
            )
        if self.name == "youtube":
            warnings.append(
                "Public YouTube video statistics are global and not exact India-only views."
            )
        if self.name == "wikimedia":
            warnings.append(
                "Wikipedia activity indicates information seeking, not content consumption."
            )

        return SourceEvidence(
            source=self.name,
            status=status,
            freshness_score=0.82 if status == "cached" else 0.94,
            quality_score=0.8 + 0.1 * math.sin(value),
            metrics={k: round(v, 2) for k, v in metrics_by_source[self.name].items()},
            warnings=warnings,
            provenance={
                "mode": "deterministic-offline-demo",
                "title": title.name,
                "adapter_version": "0.1.0",
            },
        )


class DemoSourceRegistry:
    SOURCE_NAMES = (
        "google_trends",
        "youtube",
        "wikimedia",
        "anilist",
        "regional_context",
    )

    def collect(
        self, title: Title, disabled_sources: set[str] | None = None
    ) -> list[SourceEvidence]:
        disabled_sources = disabled_sources or set()
        return [
            DemoAdapter(name, "unavailable").collect(title)
            if name in disabled_sources
            else RegionalContextCensus().collect(title)  # real census-derived, even offline
            if name == "regional_context"
            else DemoAdapter(name).collect(title)
            for name in self.SOURCE_NAMES
        ]
