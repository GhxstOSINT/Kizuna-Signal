from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Title
from app.db.session import get_db
from app.schemas.asset import AssetCreate, AssetOut
from app.schemas.assumption import AssumptionIn, AssumptionOut
from app.schemas.completeness import CompletenessReport
from app.schemas.title import TitleCreate, TitleOut
from app.services import assets as asset_service
from app.services import assumptions as assumption_service
from app.services import completeness as completeness_service
from app.services import projects as project_service
from app.services import titles as title_service

router = APIRouter(prefix="/titles", tags=["titles"])


def _title_or_404(db: Session, title_id: int) -> Title:
    title = title_service.get(db, title_id)
    if title is None:
        raise HTTPException(404, "Title not found")
    return title


@router.post("", response_model=TitleOut, status_code=201)
def create_title(body: TitleCreate, db: Session = Depends(get_db)):
    if project_service.get(db, body.project_id) is None:
        raise HTTPException(422, f"project_id {body.project_id} does not exist")
    return title_service.create(db, body)


@router.get("/{title_id}", response_model=TitleOut)
def get_title(title_id: int, db: Session = Depends(get_db)):
    return _title_or_404(db, title_id)


@router.post("/{title_id}/assets", response_model=AssetOut, status_code=201)
def add_asset(title_id: int, body: AssetCreate, db: Session = Depends(get_db)):
    _title_or_404(db, title_id)
    return asset_service.create(db, title_id, body)


@router.get("/{title_id}/assets", response_model=list[AssetOut])
def list_assets(title_id: int, db: Session = Depends(get_db)):
    _title_or_404(db, title_id)
    return asset_service.list_for_title(db, title_id)


@router.put("/{title_id}/assumptions", response_model=AssumptionOut)
def put_assumptions(title_id: int, body: AssumptionIn, db: Session = Depends(get_db)):
    _title_or_404(db, title_id)
    return assumption_service.upsert(db, title_id, body)


@router.get("/{title_id}/assumptions", response_model=AssumptionOut)
def get_assumptions(title_id: int, db: Session = Depends(get_db)):
    _title_or_404(db, title_id)
    assumption = assumption_service.get(db, title_id)
    if assumption is None:
        raise HTTPException(404, "No assumptions recorded for this title")
    return assumption


@router.get("/{title_id}/completeness", response_model=CompletenessReport)
def get_completeness(title_id: int, db: Session = Depends(get_db)):
    return completeness_service.for_title(db, _title_or_404(db, title_id))
