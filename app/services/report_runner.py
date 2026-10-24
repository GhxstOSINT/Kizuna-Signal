"""Report jobs: rebuild the prediction for an analysed title, render it, store the file."""
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Analysis, Job, Report, Title, TitleAssumption
from app.ml.state_model import StateModel
from app.ml.success import SuccessModel
from app.reports import build
from app.reports.render import RENDER
from app.services import jobs as job_service
from app.services import seo as seo_service
from app.services.state_scoring import to_frame


def _title_facts(title: Title, assumption: TitleAssumption | None) -> dict:
    return {"name_en": title.name_en, "name_jp": title.name_jp, "format": title.format,
            "genres": list(title.genres or []), "tags": [], "studio": title.studio,
            "release_date": str(title.release_date) if title.release_date else None,
            "episodes": None, "minutes_per_episode": None,
            "localization_mode": assumption.localization_mode if assumption else None,
            "synopsis": title.synopsis}


def run(db: Session, job: Job, model: StateModel, success: SuccessModel | None, out_dir: Path) -> Report | None:
    report = db.scalar(select(Report).where(Report.job_id == job.id))
    if report is None:
        job_service.mark_failed(db, job, "ReportMissing", "no report row for this job")
        return None
    job_service.mark_running(db, job)
    report.status = "running"
    db.commit()
    try:
        analysis = db.get(Analysis, report.analysis_id)
        title = db.get(Title, analysis.title_id)
        assumption = db.scalar(select(TitleAssumption).where(TitleAssumption.title_id == title.id))
        frame = to_frame(title, assumption)
        result = model.predict(frame)
        seo_job = seo_service.latest(db, title.id)
        seo = seo_job.result if seo_job is not None and seo_job.status == "succeeded" else None
        out = build.prediction_out(result, title.name_en,
                                   success.score(model, frame, result["states"], Path(settings.models_dir) / "state" / model.version)
                                   if success else None, seo)
        data = RENDER[report.format](build.assemble(_title_facts(title, assumption), out, out["success"], model))
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"report_{report.id}.{report.format}"
        path.write_bytes(data)
        report.file_uri, report.status = str(path), "succeeded"
        db.commit()
        job_service.mark_succeeded(db, job, {"report_id": report.id, "bytes": len(data)})
    except Exception as exc:
        db.rollback()
        report.status = "failed"
        db.commit()
        job_service.mark_failed(db, job, type(exc).__name__, str(exc)[:500])
    return report
