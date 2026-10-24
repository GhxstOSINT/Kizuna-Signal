from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Analysis, RegionalScore
from app.services import idempotency
from app.services import jobs as job_service
from app.services import sources as source_service


def get(db: Session, analysis_id: int) -> Analysis | None:
    return db.get(Analysis, analysis_id)


def request(db: Session, title_id: int, key: str | None) -> tuple[Analysis, bool]:
    """Queue an analysis; a repeated Idempotency-Key returns the original."""

    def build() -> Analysis:
        job = job_service.add(db, "analysis", {"title_id": title_id})
        return Analysis(
            title_id=title_id,
            job_id=job.id,
            idempotency_key=key,
            disabled_sources=source_service.disabled_names(db),
        )

    return idempotency.create_once(db, Analysis, {"title_id": title_id}, key, build)


def regions(db: Session, analysis_id: int, region_type: str | None) -> list[RegionalScore]:
    stmt = (
        select(RegionalScore)
        .where(RegionalScore.analysis_id == analysis_id)
        .order_by(RegionalScore.region_type, RegionalScore.rank)
    )
    if region_type is not None:
        stmt = stmt.where(RegionalScore.region_type == region_type)
    return list(db.scalars(stmt))
