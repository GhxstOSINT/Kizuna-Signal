"""Runs a queued analysis through the state model and stores the result.

Only state-level output is produced here. `market_potential` stays empty: it belongs to a
separate model, and the state model's job is the regional split and its confidence.
"""
from datetime import date, datetime, timezone

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Analysis, Job, RegionalScore, Title, TitleAssumption
from app.ml.features import titles_frame
from app.ml.schema import TitleRecord
from app.ml.state_model import StateModel
from app.services import jobs as job_service

FORMATS = {"anime_series": "TV", "anime_film": "MOVIE"}


def to_frame(title: Title, assumption: TitleAssumption | None) -> pd.DataFrame:
    """One-row title frame. The DB has no themes or episode count, so those features are empty."""
    launch = (assumption.planned_launch_date if assumption else None) or title.release_date or date.today()
    record = TitleRecord(
        title_id=f"db:{title.id}",
        franchise_id=f"db:{title.franchise or title.id}",
        english_title=title.name_en, japanese_title=title.name_jp,
        genres=list(title.genres or []), themes=[],
        format=FORMATS.get(title.format or "", title.format),
        original_release_date=launch, synopsis=title.synopsis or "",
    )
    frame = titles_frame([record])
    return frame.assign(studio=title.studio, has_prequel=False, minutes=0.0)


def score(model: StateModel, title: Title, assumption: TitleAssumption | None) -> dict:
    return model.predict(to_frame(title, assumption))


def store(db: Session, analysis: Analysis, result: dict, target_states: list[str]) -> None:
    """Replace any earlier regional rows so a re-run never duplicates them."""
    for old in db.scalars(select(RegionalScore).where(RegionalScore.analysis_id == analysis.id)):
        db.delete(old)
    targets = set(target_states)
    for row in result["states"]:
        db.add(RegionalScore(
            analysis_id=analysis.id, region_type="state", region_code=row["state"], region_name=row["name"],
            score=row["lift"], rank=row["rank"],
            confidence=result["confidence"],
            evidence=[{"expected_share": row["expected_share"], "interval": [row["low"], row["high"]],
                       "train_titles": row["train_titles"], "in_target": row["state"] in targets,
                       "drivers": row["drivers"]}],
        ))
    analysis.status = "succeeded"
    analysis.result_version = result["model_version"]
    analysis.confidence = result["confidence"]
    analysis.warning_codes = result["warnings"]
    analysis.provenance_summary = {
        "task": result["task"], "model_version": result["model_version"],
        "confidence_factors": result["confidence_factors"], "comparables": result["comparables"],
        "history_titles": result["history_titles"],
        "score_meaning": "lift (log scale): >0 means the title is expected to over-perform in that state "
                         "versus a typical anime there; ranks are by lift",
    }
    analysis.completed_at = datetime.now(timezone.utc)


def run_analysis(db: Session, analysis: Analysis, model: StateModel) -> Analysis:
    job = db.get(Job, analysis.job_id) if analysis.job_id else None
    if job is not None:
        job_service.mark_running(db, job)
    analysis.status = "running"
    db.commit()
    try:
        title = db.get(Title, analysis.title_id)
        assumption = db.scalar(select(TitleAssumption).where(TitleAssumption.title_id == analysis.title_id))
        result = score(model, title, assumption)
        store(db, analysis, result, list(assumption.target_states) if assumption else [])
        db.commit()
        if job is not None:
            job_service.mark_succeeded(db, job, {"analysis_id": analysis.id, "model_version": model.version})
    except Exception as exc:  # recorded on the job so the API can report it; the worker keeps going
        db.rollback()
        analysis.status = "failed"
        db.commit()
        if job is not None:
            job_service.mark_failed(db, job, type(exc).__name__, str(exc)[:500])
    return analysis


def process_queued(db: Session, model: StateModel, limit: int = 10) -> int:
    """Run queued analyses oldest first. Returns how many were processed."""
    queued = list(db.scalars(select(Analysis).where(Analysis.status == "queued")
                             .order_by(Analysis.id).limit(limit)))
    for analysis in queued:
        run_analysis(db, analysis, model)
    return len(queued)
