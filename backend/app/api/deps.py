"""Request dependencies: who is signed in, and lookups that only ever return their own data."""

from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Analysis, Job, Project, Title, User
from app.db.session import get_db
from app.services.auth.sessions import COOKIE, user_for_token


def current_user(
    token: str | None = Cookie(default=None, alias=COOKIE),
    db: Session = Depends(get_db),
) -> User:
    user = user_for_token(db, token)
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to continue")
    return user


# Someone else's record is reported exactly like a missing one, so ids cannot be probed.
def owned_project(db: Session, user: User, project_id: str) -> Project:
    project = db.scalar(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def owned_title(db: Session, user: User, title_id: str) -> Title:
    title = db.scalar(
        select(Title)
        .join(Project, Title.project_id == Project.id)
        .where(Title.id == title_id, Project.owner_id == user.id)
    )
    if title is None:
        raise HTTPException(status_code=404, detail="Title not found")
    return title


def owned_analysis(db: Session, user: User, analysis_id: str) -> Analysis:
    analysis = db.scalar(
        select(Analysis)
        .join(Title, Analysis.title_id == Title.id)
        .join(Project, Title.project_id == Project.id)
        .where(Analysis.id == analysis_id, Project.owner_id == user.id)
    )
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


def owned_job(db: Session, user: User, job_id: str) -> Job:
    job = db.scalar(
        select(Job)
        .join(Analysis, Job.analysis_id == Analysis.id)
        .join(Title, Analysis.title_id == Title.id)
        .join(Project, Title.project_id == Project.id)
        .where(Job.id == job_id, Project.owner_id == user.id)
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
