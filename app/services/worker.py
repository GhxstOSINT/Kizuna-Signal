"""One pass over every kind of queued work: state analyses, SEO jobs, collection jobs."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.google_trends import TrendsClient
from app.db.models import Job
from app.ml.state_model import StateModel
from app.services import collection, seo, state_scoring


def process_all(db: Session, model: StateModel | None, trends: TrendsClient, limit: int = 10) -> dict[str, int]:
    done = {"analysis": 0, "seo": 0, "collection": 0}
    if model is not None:
        done["analysis"] = state_scoring.process_queued(db, model, limit)
    for kind, runner in (("seo", seo.run), ("collection", collection.run)):
        jobs = list(db.scalars(select(Job).where(Job.job_type == kind, Job.status == "queued")
                               .order_by(Job.id).limit(limit)))
        for job in jobs:
            runner(db, job, trends)
        done[kind] = len(jobs)
    return done
