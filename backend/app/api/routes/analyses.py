from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Analysis, Job, Scenario, Title
from app.db.session import get_db
from app.schemas.analysis import (
    AnalysisCreated,
    AnalysisRead,
    AnalysisResult,
    JobRead,
    SourceToggleRequest,
)
from app.schemas.scenario import ScenarioCreate, ScenarioRead
from app.services.analysis import create_analysis, run_analysis_pipeline
from app.services.scenarios import run_scenario

router = APIRouter()


@router.post(
    "/titles/{title_id}/analyses",
    response_model=AnalysisCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_analysis(
    title_id: str,
    background_tasks: BackgroundTasks,
    payload: SourceToggleRequest | None = None,
    db: Session = Depends(get_db),
) -> AnalysisCreated:
    title = db.get(Title, title_id)
    if title is None:
        raise HTTPException(status_code=404, detail="Title not found")
    analysis, job = create_analysis(db, title)
    disabled_sources = payload.disabled_sources if payload else []
    background_tasks.add_task(run_analysis_pipeline, analysis.id, disabled_sources)
    return AnalysisCreated(analysis_id=analysis.id, job_id=job.id, status=analysis.status)


@router.get("/titles/{title_id}/analyses", response_model=list[AnalysisRead])
def list_analyses(title_id: str, db: Session = Depends(get_db)) -> list[Analysis]:
    if db.get(Title, title_id) is None:
        raise HTTPException(status_code=404, detail="Title not found")
    return list(
        db.scalars(
            select(Analysis)
            .where(Analysis.title_id == title_id)
            .order_by(Analysis.created_at.desc())
        )
    )


@router.get("/analyses/{analysis_id}", response_model=AnalysisRead)
def get_analysis(analysis_id: str, db: Session = Depends(get_db)) -> Analysis:
    analysis = db.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


@router.delete("/analyses/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis(analysis_id: str, db: Session = Depends(get_db)) -> None:
    """Delete an analysis with its job and scenarios.

    A title with no analyses left would be invisible in the portfolio, so it is removed too.
    """
    analysis = db.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    title = analysis.title
    db.delete(analysis)
    db.flush()
    db.refresh(title)
    if not title.analyses:
        db.delete(title)
    db.commit()


@router.get("/analyses/{analysis_id}/result", response_model=AnalysisResult)
def get_analysis_result(analysis_id: str, db: Session = Depends(get_db)) -> AnalysisResult:
    analysis = db.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.result is None:
        raise HTTPException(status_code=409, detail=f"Analysis is {analysis.status}")
    return AnalysisResult.model_validate(analysis.result)


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: str, db: Session = Depends(get_db)) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post(
    "/analyses/{analysis_id}/scenarios",
    response_model=ScenarioRead,
    status_code=status.HTTP_201_CREATED,
)
def create_scenario(
    analysis_id: str,
    payload: ScenarioCreate,
    db: Session = Depends(get_db),
) -> Scenario:
    analysis = db.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.result is None:
        raise HTTPException(status_code=409, detail="Analysis has not completed")
    title = db.get(Title, analysis.title_id)
    if title is None:
        raise HTTPException(status_code=404, detail="Title not found")
    base = AnalysisResult.model_validate(analysis.result)
    result = run_scenario(title, base, payload)
    scenario = Scenario(
        analysis_id=analysis.id,
        name=payload.name,
        overrides=payload.model_dump(exclude_none=True, mode="json"),
        result=result.model_dump(mode="json"),
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return scenario


@router.get("/analyses/{analysis_id}/scenarios", response_model=list[ScenarioRead])
def list_scenarios(analysis_id: str, db: Session = Depends(get_db)) -> list[Scenario]:
    if db.get(Analysis, analysis_id) is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return list(
        db.scalars(
            select(Scenario)
            .where(Scenario.analysis_id == analysis_id)
            .order_by(Scenario.created_at.desc())
        )
    )
