from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.routes.analyses import IdempotencyKey
from app.db.session import get_db
from app.schemas.pipeline import JobOut
from app.services import seo as seo_service
from app.services import titles as title_service

router = APIRouter(prefix="/titles", tags=["seo"])


@router.post("/{title_id}/seo", response_model=JobOut, status_code=202)
def request_seo(title_id: int, response: Response, idempotency_key: IdempotencyKey = None,
                db: Session = Depends(get_db)):
    if title_service.get(db, title_id) is None:
        raise HTTPException(404, "Title not found")
    job, created = seo_service.request(db, title_id, idempotency_key)
    if not created:
        response.status_code = 200  # replayed request: original job returned
    return job


@router.get("/{title_id}/seo")
def get_seo(title_id: int, db: Session = Depends(get_db)) -> dict:
    """Latest SEO result. 404 if never requested; 409 while the job is not finished."""
    if title_service.get(db, title_id) is None:
        raise HTTPException(404, "Title not found")
    job = seo_service.latest(db, title_id)
    if job is None:
        raise HTTPException(404, "No SEO analysis requested for this title")
    if job.status != "succeeded":
        raise HTTPException(409, {"job_id": job.id, "status": job.status, "error_code": job.error_code})
    return {"job_id": job.id, **job.result}
