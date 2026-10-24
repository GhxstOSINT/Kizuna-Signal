from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings
from app.services.sources import DemoSourceRegistry

router = APIRouter()


@router.get("/health")
def source_health() -> dict:
    settings = get_settings()
    return {
        "mode": "offline-safe-demo" if settings.demo_mode else "configured-live",
        "sources": [
            {
                "source": name,
                "status": "cached" if name == "google_trends" else "available",
                "required": False,
            }
            for name in DemoSourceRegistry.SOURCE_NAMES
        ],
        "policy": "Optional source failure lowers confidence but does not fabricate evidence.",
    }
