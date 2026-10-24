from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Project
from app.schemas.project import ProjectCreate


def create(db: Session, body: ProjectCreate) -> Project:
    project = Project(**body.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def get(db: Session, project_id: int) -> Project | None:
    return db.get(Project, project_id)


def list_all(db: Session, skip: int = 0, limit: int = 100) -> list[Project]:
    stmt = select(Project).order_by(Project.id).offset(skip).limit(limit)
    return list(db.scalars(stmt))
