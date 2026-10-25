from __future__ import annotations

import importlib.util

from fastapi import APIRouter

from app.core.config import get_settings
from app.services.sources import DemoSourceRegistry

router = APIRouter()


def _live_status(name: str, settings) -> str:
    if name == "youtube":
        return "available" if settings.youtube_api_key else "unconfigured"
    if name == "google_trends":
        return "available" if importlib.util.find_spec("pytrends") else "unconfigured"
    return "available"


@router.get("/health")
def source_health() -> dict:
    settings = get_settings()
    if settings.live_sources:
        return {
            "mode": "live-public-apis",
            "sources": [
                {"source": name, "status": _live_status(name, settings), "required": False}
                for name in DemoSourceRegistry.SOURCE_NAMES
            ],
            "policy": "Optional source failure lowers confidence but does not fabricate evidence.",
        }
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
