from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Project, Title
from app.db.session import get_db
from app.schemas.project import ProjectCreate, ProjectRead, TitleCreate, TitleRead

router = APIRouter()


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    project = Project(**payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db)) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.created_at.desc())))


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, db: Session = Depends(get_db)) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/{project_id}/titles", response_model=TitleRead, status_code=status.HTTP_201_CREATED)
def create_title(project_id: str, payload: TitleCreate, db: Session = Depends(get_db)) -> Title:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    data = payload.model_dump()
    if data.get("trailer_url") is not None:
        data["trailer_url"] = str(data["trailer_url"])
    title = Title(project_id=project_id, **data)
    db.add(title)
    db.commit()
    db.refresh(title)
    return title


@router.get("/{project_id}/titles", response_model=list[TitleRead])
def list_titles(project_id: str, db: Session = Depends(get_db)) -> list[Title]:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return list(
        db.scalars(
            select(Title).where(Title.project_id == project_id).order_by(Title.created_at.desc())
        )
    )
