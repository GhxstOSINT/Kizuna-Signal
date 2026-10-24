"""Paths and constants shared across the app."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOCK_DIR = ROOT / "data" / "mock"
GEO_PATH = ROOT / "data" / "geo" / "india_states.geojson"
GEO_KEY = "properties.ST_NM"

# Simulated seconds per pipeline stage on the progress screen.
STAGE_SECONDS = 0.7

APP_NAME = "Kizuna Signal"
