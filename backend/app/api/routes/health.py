from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.services.model_analysis import current_model_version

router = APIRouter()


@router.get("/health/live")
def liveness() -> dict:
    return {"status": "ok", "service": "kizuna-signal-api"}


@router.get("/health/ready")
def readiness(db: Session = Depends(get_db)):
    settings = get_settings()
    trained_version = current_model_version()
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "database": "unavailable",
                "model_version": trained_version or settings.model_version,
                "model_status": "ready" if trained_version else "fallback",
                "feature_version": settings.feature_version,
                "scoring_version": settings.scoring_version,
            },
        )
    return {
        "status": "ready",
        "database": "available",
        "demo_mode": settings.demo_mode,
        "model_version": trained_version or settings.model_version,
        "model_status": "ready" if trained_version else "fallback",
        "feature_version": settings.feature_version,
        "scoring_version": settings.scoring_version,
    }
