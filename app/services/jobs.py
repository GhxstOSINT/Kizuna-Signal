from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import Job


def _now() -> datetime:
    return datetime.now(timezone.utc)


def add(db: Session, job_type: str, payload: dict) -> Job:
    """Stage a queued job in the caller's transaction (flushed so it has an id)."""
    job = Job(job_type=job_type, status="queued", payload=payload)
    db.add(job)
    db.flush()
    return job


def get(db: Session, job_id: int) -> Job | None:
    return db.get(Job, job_id)


# Worker-side transitions (used by the ML/ingestion workers).
def mark_running(db: Session, job: Job) -> Job:
    job.status, job.started_at = "running", _now()
    db.commit()
    return job


def mark_succeeded(db: Session, job: Job, result: dict | None = None) -> Job:
    job.status, job.result, job.finished_at = "succeeded", result, _now()
    db.commit()
    return job


def mark_failed(db: Session, job: Job, code: str, message: str) -> Job:
    job.status, job.error_code, job.error_message = "failed", code, message
    job.finished_at = _now()
    db.commit()
    return job
