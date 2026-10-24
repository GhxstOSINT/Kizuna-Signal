"""Paths and constants shared across the app."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOCK_DIR = ROOT / "data" / "mock"
GEO_PATH = ROOT / "data" / "geo" / "india_states.geojson"
GEO_KEY = "properties.ST_NM"

# Simulated seconds per pipeline stage on the progress screen.
STAGE_SECONDS = 0.7

APP_NAME = "Kizuna Signal"
API_URL = os.getenv("KIZUNA_API_URL", "http://localhost:8000/api/v1").rstrip("/")
FRONTEND_MODE = os.getenv("KIZUNA_FRONTEND_MODE", "auto").lower()
