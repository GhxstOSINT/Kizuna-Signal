from sqlalchemy.orm import Session

from app.db.models import Report
from app.schemas.pipeline import ReportCreate
from app.services import idempotency
from app.services import jobs as job_service


def get(db: Session, report_id: int) -> Report | None:
    return db.get(Report, report_id)


def request(db: Session, body: ReportCreate, key: str | None) -> tuple[Report, bool]:
    """Queue report generation; a repeated Idempotency-Key returns the original."""

    def build() -> Report:
        job = job_service.add(
            db, "report", {"analysis_id": body.analysis_id, "format": body.format.value}
        )
        return Report(
            analysis_id=body.analysis_id,
            job_id=job.id,
            idempotency_key=key,
            format=body.format.value,
        )

    return idempotency.create_once(db, Report, {"analysis_id": body.analysis_id}, key, build)
