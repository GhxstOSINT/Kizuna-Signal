from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import TitleAssumption
from app.schemas.assumption import AssumptionIn


def get(db: Session, title_id: int) -> TitleAssumption | None:
    return db.scalar(select(TitleAssumption).where(TitleAssumption.title_id == title_id))


def upsert(db: Session, title_id: int, body: AssumptionIn) -> TitleAssumption:
    row = get(db, title_id) or TitleAssumption(title_id=title_id)
    for key, value in body.model_dump(mode="json").items():
        setattr(row, key, value)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
