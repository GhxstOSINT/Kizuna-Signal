from __future__ import annotations

from fastapi import APIRouter

from app.ml import regional

router = APIRouter()


@router.get("/card")
def model_card() -> dict:
    """Training provenance and honest evaluation for the state-demand model."""
    artifact = regional.load()
    if artifact is None:
        return {"active": False, "model_version": None}
    return {
        "active": True,
        "model_version": artifact["model_version"],
        "model": artifact["model"],
        "target": artifact["target"],
        "dataset": artifact["dataset"],
        "metrics": artifact["metrics"],
        "conformal": artifact["conformal"],
    }
