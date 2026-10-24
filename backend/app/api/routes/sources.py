from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings
from app.services.sources import SourceRegistry

router = APIRouter()


@router.get("/health")
def source_health() -> dict:
    settings = get_settings()
    registry = SourceRegistry(settings)
    return {
        "mode": "offline-safe-demo" if settings.demo_mode else "configured-live",
        "sources": [
            {
                "source": name,
                "status": (
                    "unavailable"
                    if registry.mode_for(name) == "unconfigured"
                    else "cached"
                    if name == "google_trends" and registry.mode_for(name) == "demo"
                    else "available"
                ),
                "mode": registry.mode_for(name),
                "required": False,
            }
            for name in registry.SOURCE_NAMES
        ],
        "policy": "Optional source failure lowers confidence but does not fabricate evidence.",
    }
