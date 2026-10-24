from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.sources import KNOWN_SOURCES
from app.db.session import get_db
from app.schemas.pipeline import CollectRequest, JobOut, SourceOut, SourceRunOut, SourceUpdate
from app.services import sources as source_service
from app.services import titles as title_service

router = APIRouter(prefix="/sources", tags=["sources"])


@router.post("/collect", response_model=JobOut, status_code=202)
def collect(body: CollectRequest, db: Session = Depends(get_db)):
    if title_service.get(db, body.title_id) is None:
        raise HTTPException(404, "Title not found")
    try:
        return source_service.request_collection(db, body.title_id, body.sources)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/health", response_model=list[SourceOut])
def source_health(db: Session = Depends(get_db)):
    return source_service.list_all(db)


@router.get("/runs", response_model=list[SourceRunOut])
def source_runs(
    title_id: int | None = None,
    source: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Provenance: which source was collected for which title, when, from cache or live."""
    if source is not None and source not in KNOWN_SOURCES:
        raise HTTPException(422, f"unknown source: {source}")
    return source_service.runs(db, title_id, source, min(limit, 500))


@router.patch("/{name}", response_model=SourceOut)
def update_source(name: str, body: SourceUpdate, db: Session = Depends(get_db)):
    """Enable or disable a source, e.g. to silence a noisy one."""
    source = source_service.set_enabled(db, name, body.enabled)
    if source is None:
        raise HTTPException(404, "Source not found")
    return source
