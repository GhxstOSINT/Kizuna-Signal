"""Filesystem anchors for the monorepo.

Data, trained models and docs live outside ``backend/``. Code that needs them imports the
constants below instead of building relative paths, so it works from any working directory.

``KIZUNA_ROOT`` overrides discovery (the Docker image sets it, because the installed package is
not inside a checkout).
"""

from __future__ import annotations

import os
from pathlib import Path


def _find_repo_root() -> Path:
    override = os.environ.get("KIZUNA_ROOT")
    if override:
        return Path(override).resolve()
    for parent in Path(__file__).resolve().parents:
        if (parent / "backend" / "app").is_dir():
            return parent
    return Path.cwd()


REPO_ROOT = _find_repo_root()
BACKEND_DIR = REPO_ROOT / "backend"
DATA_DIR = REPO_ROOT / "data"
TABLES_DIR = DATA_DIR / "tables"  # state-model training tables (data_dictionary.csv describes them)
MODELS_DIR = REPO_ROOT / "models"  # trained artifacts: models/state/<version>/
DOCS_DIR = REPO_ROOT / "docs"
REPORTS_DIR = DOCS_DIR / "reports"  # generated model/region reports and figures
OPENAPI_SNAPSHOT = DOCS_DIR / "openapi.json"


def resolve(path: str | Path) -> Path:
    """Absolute paths are kept; relative ones are taken from the repo root, not the cwd."""
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate
