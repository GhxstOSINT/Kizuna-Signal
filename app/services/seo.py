"""SEO insight jobs: queue, run, read back. Results live in Job.result (no extra table)."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.google_trends import TrendsClient
from app.db.models import Analysis, Job, RegionalScore, Title, TitleAssumption
from app.seo import rank as seo_rank
from app.seo.terms import candidates
from app.services import jobs as job_service

JOB_TYPE = "seo"
STATE_FOCUS = 3


def request(db: Session, title_id: int, key: str | None) -> tuple[Job, bool]:
    """Queue an SEO job. A repeated Idempotency-Key for the same title returns the original job."""
    if key is not None:
        existing = db.scalar(select(Job).where(
            Job.job_type == JOB_TYPE, Job.payload["title_id"].as_integer() == title_id,
            Job.payload["idempotency_key"].as_string() == key))
        if existing is not None:
            return existing, False
    job = job_service.add(db, JOB_TYPE, {"title_id": title_id, "idempotency_key": key})
    db.commit()
    db.refresh(job)
    return job, True


def latest(db: Session, title_id: int) -> Job | None:
    return db.scalar(select(Job).where(Job.job_type == JOB_TYPE, Job.payload["title_id"].as_integer() == title_id)
                     .order_by(Job.id.desc()).limit(1))


def _state_focus(db: Session, title_id: int) -> list[RegionalScore]:
    analysis = db.scalar(select(Analysis).where(Analysis.title_id == title_id, Analysis.status == "succeeded")
                         .order_by(Analysis.id.desc()).limit(1))
    if analysis is None:
        return []
    return list(db.scalars(select(RegionalScore).where(
        RegionalScore.analysis_id == analysis.id, RegionalScore.region_type == "state")
        .order_by(RegionalScore.rank).limit(STATE_FOCUS)))


def compute(db: Session, title: Title, assumption: TitleAssumption | None, client: TrendsClient, today: date) -> dict:
    cands = candidates(title.name_en, title.name_jp, list(assumption.languages) if assumption else [],
                       assumption.localization_mode if assumption else None)
    ranked = seo_rank.rank(client, cands, today)
    ok = [r for r in ranked if r["status"] == "ok"]
    best = ok[0]["term"] if ok else None
    warnings = []
    if not ok:
        warnings.append("no_signal_any_term")
    if any(r["status"] == "blocked" for r in ranked):
        warnings.append("trends_blocked_partial_results")
    if title.is_unreleased:
        warnings.append("unreleased_title_interest_is_for_the_name_only")

    focus = []
    for score in _state_focus(db, title.id):
        entry = {"state": score.region_code, "name": score.region_name, "lift": score.score,
                 "expected_share": score.evidence[0]["expected_share"] if score.evidence else None,
                 "term_ratio": None}
        if best:
            measured = seo_rank.score_term(client, best, score.region_code, today)
            entry["term_ratio"] = measured.get("ratio") if measured["status"] == "ok" else None
            entry["term_status"] = measured["status"]
        focus.append(entry)
    if not focus:
        warnings.append("no_completed_state_analysis")
    return {"title_id": title.id, "method": seo_rank.METHOD, "as_of": str(today), "best_term": best,
            "best_by_variant": seo_rank.best_by_variant(ranked), "candidates": ranked,
            "state_focus": focus, "warnings": warnings,
            "not_available": ["search volume", "keyword difficulty", "rankings", "launch timing"]}


def run(db: Session, job: Job, client: TrendsClient, today: date | None = None) -> Job:
    job_service.mark_running(db, job)
    try:
        title = db.get(Title, job.payload["title_id"])
        assumption = db.scalar(select(TitleAssumption).where(TitleAssumption.title_id == title.id))
        return job_service.mark_succeeded(db, job, compute(db, title, assumption, client, today or date.today()))
    except Exception as exc:
        db.rollback()
        return job_service.mark_failed(db, job, type(exc).__name__, str(exc)[:500])
