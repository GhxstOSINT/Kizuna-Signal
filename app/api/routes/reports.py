from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.routes.analyses import IdempotencyKey
from app.db.session import get_db
from app.schemas.pipeline import JobOut, ReportCreate, ReportOut
from app.services import analyses as analysis_service
from app.services import jobs as job_service
from app.services import reports as report_service

router = APIRouter(tags=["reports"])


@router.post("/reports", response_model=ReportOut, status_code=202)
def create_report(
    body: ReportCreate,
    response: Response,
    idempotency_key: IdempotencyKey = None,
    db: Session = Depends(get_db),
):
    analysis = analysis_service.get(db, body.analysis_id)
    if analysis is None:
        raise HTTPException(404, "Analysis not found")
    if analysis.status != "succeeded":
        raise HTTPException(409, f"Analysis is {analysis.status}, not complete")
    report, created = report_service.request(db, body, idempotency_key)
    if not created:
        response.status_code = 200
    return report


@router.get("/reports/{report_id}", response_model=ReportOut)
def get_report(report_id: int, db: Session = Depends(get_db)):
    report = report_service.get(db, report_id)
    if report is None:
        raise HTTPException(404, "Report not found")
    return report


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    """Poll asynchronous work; failures carry error_code and error_message."""
    job = job_service.get(db, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return job
