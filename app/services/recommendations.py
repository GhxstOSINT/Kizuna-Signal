from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Recommendation


def list_for_analysis(db: Session, analysis_id: int) -> list[Recommendation]:
    stmt = (
        select(Recommendation)
        .where(Recommendation.analysis_id == analysis_id)
        .order_by(Recommendation.category, Recommendation.id)
    )
    return list(db.scalars(stmt))


def get(db: Session, recommendation_id: int) -> Recommendation | None:
    return db.get(Recommendation, recommendation_id)


def decide(db: Session, rec: Recommendation, status: str, decided_by: str) -> Recommendation:
    rec.status, rec.decided_by = status, decided_by
    rec.decided_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(rec)
    return rec
