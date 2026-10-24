from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import TitleAsset
from app.schemas.asset import AssetCreate


def create(db: Session, title_id: int, body: AssetCreate) -> TitleAsset:
    asset = TitleAsset(title_id=title_id, **body.model_dump(mode="json"))
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def list_for_title(db: Session, title_id: int) -> list[TitleAsset]:
    stmt = select(TitleAsset).where(TitleAsset.title_id == title_id).order_by(TitleAsset.id)
    return list(db.scalars(stmt))
