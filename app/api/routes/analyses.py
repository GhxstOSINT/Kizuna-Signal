from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.orm import Session

from app.db.models import Analysis
from app.db.session import get_db
from app.schemas.enums import RegionType
from app.schemas.pipeline import (
    AnalysisOut,
    RecommendationDecision,
    RecommendationOut,
    RegionalScoreOut,
    ScenarioCreate,
    ScenarioOut,
)
from app.services import analyses as analysis_service
from app.services import completeness as completeness_service
from app.services import recommendations as recommendation_service
from app.services import scenarios as scenario_service
from app.services import titles as title_service

router = APIRouter(tags=["analyses"])

IdempotencyKey = Annotated[
    str | None,
    Header(alias="Idempotency-Key", min_length=1, max_length=128),
]


def _analysis_or_404(db: Session, analysis_id: int) -> Analysis:
    analysis = analysis_service.get(db, analysis_id)
    if analysis is None:
        raise HTTPException(404, "Analysis not found")
    return analysis


def _completed(db: Session, analysis_id: int) -> Analysis:
    """Results exist only once the analysis job has succeeded."""
    analysis = _analysis_or_404(db, analysis_id)
    if analysis.status != "succeeded":
        raise HTTPException(409, f"Analysis is {analysis.status}, not complete")
    return analysis


@router.post("/titles/{title_id}/analyse", response_model=AnalysisOut, status_code=202)
def analyse_title(
    title_id: int,
    response: Response,
    idempotency_key: IdempotencyKey = None,
    db: Session = Depends(get_db),
):
    title = title_service.get(db, title_id)
    if title is None:
        raise HTTPException(404, "Title not found")
    report = completeness_service.for_title(db, title)
    if not report.ready_for_analysis:
        raise HTTPException(
            422,
            {
                "code": "incomplete_title",
                "message": "Title intake is incomplete",
                "missing_required": [m.model_dump() for m in report.missing_required],
            },
        )
    analysis, created = analysis_service.request(db, title_id, idempotency_key)
    if not created:
        response.status_code = 200  # replayed request: original analysis returned
    return analysis


@router.get("/analyses/{analysis_id}", response_model=AnalysisOut)
def get_analysis(analysis_id: int, db: Session = Depends(get_db)):
    return _analysis_or_404(db, analysis_id)


@router.get("/analyses/{analysis_id}/regions", response_model=list[RegionalScoreOut])
def get_regions(
    analysis_id: int, region_type: RegionType | None = None, db: Session = Depends(get_db)
):
    _completed(db, analysis_id)
    return analysis_service.regions(db, analysis_id, region_type.value if region_type else None)


@router.post("/analyses/{analysis_id}/scenarios", response_model=ScenarioOut, status_code=202)
def create_scenario(analysis_id: int, body: ScenarioCreate, db: Session = Depends(get_db)):
    _completed(db, analysis_id)
    return scenario_service.create(db, analysis_id, body)


@router.get("/analyses/{analysis_id}/scenarios", response_model=list[ScenarioOut])
def list_scenarios(analysis_id: int, db: Session = Depends(get_db)):
    _analysis_or_404(db, analysis_id)
    return scenario_service.list_for_analysis(db, analysis_id)


@router.get("/analyses/{analysis_id}/recommendation", response_model=list[RecommendationOut])
def get_recommendation(analysis_id: int, db: Session = Depends(get_db)):
    _completed(db, analysis_id)
    return recommendation_service.list_for_analysis(db, analysis_id)


@router.post("/recommendations/{recommendation_id}/decision", response_model=RecommendationOut)
def decide_recommendation(
    recommendation_id: int, body: RecommendationDecision, db: Session = Depends(get_db)
):
    rec = recommendation_service.get(db, recommendation_id)
    if rec is None:
        raise HTTPException(404, "Recommendation not found")
    if rec.status != "draft":
        raise HTTPException(409, f"Recommendation already {rec.status}")
    return recommendation_service.decide(db, rec, body.status, body.decided_by)
