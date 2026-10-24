"""Executes queued /sources/collect jobs and records provenance in source_runs.

Only Google Trends has an adapter that works from a database title (it needs just the name). The other
sources are recorded as unavailable instead of silently skipped, so the run list tells the truth.
"""
from datetime import date

from sqlalchemy.orm import Session

from app.adapters.google_trends import TrendsClient
from app.db.models import Job, SourceRun, Title
from app.seo import rank as seo_rank
from app.seo.terms import base_name
from app.services import jobs as job_service
from app.services import sources as source_service

JOB_TYPE = "collection"


def _record(db: Session, job: Job, source, title_id: int, health: str, **fields) -> None:
    db.add(SourceRun(source_id=source.id, title_id=title_id, job_id=job.id, health=health, **fields))
    source.health = health
    source.last_error = "; ".join(fields.get("warnings", [])) or None


def run(db: Session, job: Job, client: TrendsClient, today: date | None = None) -> Job:
    job_service.mark_running(db, job)
    try:
        title = db.get(Title, job.payload["title_id"])
        sources = {s.name: s for s in source_service.list_all(db)}
        summary = {}
        for name in job.payload["sources"]:
            source = sources[name]
            if name == "google_trends":
                r = seo_rank.score_term(client, base_name(title.name_en), "IN", today or date.today())
                health = {"ok": "ok", "no_signal": "degraded"}.get(r["status"], "unavailable")
                _record(db, job, source, title.id, health, record_count=r.get("records", 0),
                        from_cache=r.get("from_cache", False), raw_checksum=r.get("checksum"),
                        warnings=[] if r["status"] == "ok" else [r["status"]], details={"ratio": r.get("ratio")})
                summary[name] = r["status"]
            else:
                _record(db, job, source, title.id, "unavailable", warnings=["no_adapter_for_database_titles"])
                summary[name] = "no_adapter"
        db.commit()
        return job_service.mark_succeeded(db, job, summary)
    except Exception as exc:
        db.rollback()
        return job_service.mark_failed(db, job, type(exc).__name__, str(exc)[:500])
