from sqlalchemy.orm import Session

from app.db.models import Title
from app.schemas.title import TitleCreate


def create(db: Session, body: TitleCreate) -> Title:
    title = Title(**body.model_dump())
    db.add(title)
    db.commit()
    db.refresh(title)
    return title


def get(db: Session, title_id: int) -> Title | None:
    return db.get(Title, title_id)
