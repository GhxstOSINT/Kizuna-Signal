from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user, owned_project
from app.db.models import Project, Title, User
from app.db.session import get_db
from app.schemas.project import ProjectCreate, ProjectRead, TitleCreate, TitleRead

# Every route needs a signed-in user and only ever touches that user's own portfolio.
router = APIRouter()


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Project:
    project = Project(owner_id=user.id, **payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectRead])
def list_projects(
    db: Session = Depends(get_db), user: User = Depends(current_user)
) -> list[Project]:
    return list(
        db.scalars(
            select(Project).where(Project.owner_id == user.id).order_by(Project.created_at.desc())
        )
    )


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> Project:
    return owned_project(db, user, project_id)


@router.post("/{project_id}/titles", response_model=TitleRead, status_code=status.HTTP_201_CREATED)
def create_title(
    project_id: str,
    payload: TitleCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Title:
    project = owned_project(db, user, project_id)
    data = payload.model_dump()
    if data.get("trailer_url") is not None:
        data["trailer_url"] = str(data["trailer_url"])
    title = Title(project_id=project.id, **data)
    db.add(title)
    db.commit()
    db.refresh(title)
    return title


@router.get("/{project_id}/titles", response_model=list[TitleRead])
def list_titles(
    project_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> list[Title]:
    project = owned_project(db, user, project_id)
    return list(
        db.scalars(
            select(Title).where(Title.project_id == project.id).order_by(Title.created_at.desc())
        )
    )
