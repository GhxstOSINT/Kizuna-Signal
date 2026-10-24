from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Scenario
from app.schemas.pipeline import ScenarioCreate
from app.services import jobs as job_service


def create(db: Session, analysis_id: int, body: ScenarioCreate) -> Scenario:
    overrides = body.overrides.model_dump(mode="json", exclude_none=True)
    job = job_service.add(db, "scenario", {"analysis_id": analysis_id, "overrides": overrides})
    scenario = Scenario(
        analysis_id=analysis_id, job_id=job.id, name=body.name, overrides=overrides
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return scenario


def list_for_analysis(db: Session, analysis_id: int) -> list[Scenario]:
    stmt = select(Scenario).where(Scenario.analysis_id == analysis_id).order_by(Scenario.id)
    return list(db.scalars(stmt))
