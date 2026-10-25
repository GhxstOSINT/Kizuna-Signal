from __future__ import annotations

from app.core.config import Settings
from app.services.sources.demo import DemoSourceRegistry
from app.services.sources.live import LiveSourceRegistry


def build_registry(settings: Settings) -> DemoSourceRegistry | LiveSourceRegistry:
    """Live public APIs when KIZUNA_LIVE_SOURCES is true, otherwise the offline demo adapters."""
    return LiveSourceRegistry(settings) if settings.live_sources else DemoSourceRegistry()


__all__ = ["DemoSourceRegistry", "LiveSourceRegistry", "build_registry"]
