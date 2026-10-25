from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import StateSignal, Title
from app.db.session import get_db
from app.schemas.state_signals import StateSignalImportResult, StateSignalRead
from app.services import state_signals as service

router = APIRouter()


def _title_or_404(db: Session, title_id: str) -> Title:
    title = db.get(Title, title_id)
    if title is None:
        raise HTTPException(status_code=404, detail="Title not found")
    return title


@router.post(
    "/titles/{title_id}/state-signals/import",
    response_model=StateSignalImportResult,
    status_code=status.HTTP_201_CREATED,
)
async def import_state_signals(
    title_id: str,
    file: UploadFile = File(...),
    source: str = Form("partner_import", max_length=80),
    db: Session = Depends(get_db),
) -> StateSignalImportResult:
    """Import partner, Ormax or platform analytics. CSV columns: state, metric, value, [as_of], [source]."""
    _title_or_404(db, title_id)
    raw = await file.read(service.MAX_BYTES + 1)
    if len(raw) > service.MAX_BYTES:
        raise HTTPException(status_code=413, detail="CSV is larger than 1 MB")
    try:
        rows, rejected = service.parse_csv(
            raw.decode("utf-8-sig"), source.strip() or "partner_import"
        )
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not rows:
        raise HTTPException(
            status_code=422, detail={"message": "No valid rows", "rejected": rejected[:20]}
        )
    batch = service.store_rows(db, title_id, rows, {"filename": file.filename or ""})
    return StateSignalImportResult(
        imported=len(rows),
        rejected=rejected[:50],
        rejected_count=len(rejected),
        import_batch=batch,
        state_index=service.load_partner_index(db, title_id),
    )


@router.get("/titles/{title_id}/state-signals", response_model=list[StateSignalRead])
def list_state_signals(title_id: str, db: Session = Depends(get_db)) -> list[StateSignal]:
    _title_or_404(db, title_id)
    return list(
        db.scalars(
            select(StateSignal)
            .where(StateSignal.title_id == title_id)
            .order_by(StateSignal.as_of.desc(), StateSignal.state)
            .limit(2000)
        )
    )
