from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Analysis, Job, Title
from app.db.session import SessionLocal
from app.schemas.analysis import AnalysisResult, SourceStatus
from app.services.comparables import find_comparables
from app.services.confidence import calculate_confidence, confidence_interval
from app.services.model_analysis import score_title
from app.services.recommendations import build_recommendation
from app.services.regional import calculate_regional_scores_live, has_regional_evidence
from app.services.scoring import (
    build_drivers,
    calculate_component_scores,
    calculate_market_score,
    calculate_regional_scores,
    decision_classification,
    unmeasured_components,
)
from app.services.sources import SourceRegistry
from app.services.state_signals import (
    apply_partner_tilt,
    load_partner_index,
    replace_source_for_day,
    trends_rows,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Exception text can carry SQL, paths or other internals, so the API only ever sees this message;
# the full traceback goes to the server log.
PUBLIC_FAILURE_MESSAGE = (
    "Analysis failed unexpectedly. Please retry; if it persists, contact support."
)


def utcnow() -> datetime:
    return datetime.now(UTC)


def update_job(db: Session, job: Job, progress: int, stage: str, status: str = "running") -> None:
    job.progress = max(job.progress, min(100, progress))
    job.stage = stage
    job.status = status
    job.updated_at = utcnow()
    db.commit()


def _record_trends_by_state(db: Session, title_id: str, evidence: list) -> None:
    """Keep a dated history of live Google Trends state interest in `state_signals`."""
    trends = next(
        (e for e in evidence if e.source == "google_trends" and e.status == "available"), None
    )
    if trends is not None and trends.regional:
        replace_source_for_day(
            db,
            title_id,
            "google_trends",
            trends_rows(trends.regional),
            {"terms": trends.provenance.get("terms", trends.provenance.get("keyword", ""))},
        )


def run_analysis_pipeline(analysis_id: str, disabled_sources: list[str] | None = None) -> None:
    db = SessionLocal()
    try:
        analysis = db.get(Analysis, analysis_id)
        if analysis is None or analysis.job is None:
            logger.error("analysis_not_found", extra={"analysis_id": analysis_id})
            return
        job = analysis.job
        title = db.get(Title, analysis.title_id)
        if title is None:
            raise ValueError("Title no longer exists")

        analysis.status = "running"
        update_job(db, job, 10, "collecting public evidence")

        evidence = SourceRegistry(settings).collect(title, set(disabled_sources or []))
        analysis.source_snapshot = {
            item.source: {
                "status": item.status,
                "freshness_score": item.freshness_score,
                "quality_score": item.quality_score,
                "metrics": item.metrics,
                "warnings": item.warnings,
                "provenance": item.provenance,
                **({"regional": item.regional} if item.regional else {}),
            }
            for item in evidence
        }
        db.commit()

        update_job(db, job, 35, "building content profile and comparable titles")
        comparables = find_comparables(title, evidence=evidence, allow_catalog=settings.demo_mode)

        update_job(db, job, 55, "running trained market and regional model")
        component_scores = calculate_component_scores(title, evidence, comparables)
        unmeasured = unmeasured_components(title, evidence, comparables)
        market_score = calculate_market_score(component_scores, unmeasured)
        confidence, confidence_level, warnings = calculate_confidence(
            title, evidence, comparables, unmeasured
        )
        score_origin = "deterministic_fallback"
        score_meaning = "A bounded relative market-opportunity index, not a revenue forecast."
        model_warnings: list[str] = []
        component_details: list[dict] = []
        model_evaluation: dict = {}
        regions = []

        try:
            model_result = score_title(title, confidence)
        except (FileNotFoundError, ValueError, OSError) as exc:
            logger.warning("trained_model_unavailable", extra={"reason": str(exc)})
            model_warnings.append(
                "The trained model was unavailable, so this snapshot uses the deterministic fallback."
            )
            if has_regional_evidence(evidence):
                regions = calculate_regional_scores_live(title, market_score, confidence, evidence)
            else:
                regions = calculate_regional_scores(title, market_score, confidence)
            interval = confidence_interval(market_score, confidence)
            positive, negative = build_drivers(component_scores, title, evidence, unmeasured)
        else:
            market_score = model_result.score
            confidence = model_result.confidence
            if {"demand_momentum", "engagement_quality"}.issubset(unmeasured):
                confidence = min(confidence, 44.0)
                regions = [
                    region.model_copy(update={"confidence": confidence})
                    for region in model_result.regions
                ]
            confidence_level = (
                "high" if confidence >= 75 else "medium" if confidence >= 50 else "low"
            )
            component_scores = model_result.components
            if not regions:
                regions = model_result.regions
            interval = model_result.interval
            positive = model_result.positive_drivers
            negative = model_result.negative_drivers
            model_warnings = model_result.warnings
            component_details = model_result.component_details
            model_evaluation = model_result.evaluation
            score_meaning = model_result.score_meaning
            score_origin = "trained_model"
            analysis.model_version = model_result.model_version
            analysis.scoring_version = "market-potential-trained-1.0.0"

        _record_trends_by_state(db, title.id, evidence)
        regions = apply_partner_tilt(regions, load_partner_index(db, title.id))

        update_job(db, job, 75, "generating explanations and confidence interval")
        warnings = list(dict.fromkeys([*warnings, *model_warnings]))
        classification = decision_classification(market_score, confidence)

        update_job(db, job, 90, "building launch playbook")
        recommendation = build_recommendation(title, market_score, confidence, regions)

        source_status = [
            SourceStatus(
                source=item.source,
                status=item.status,
                freshness_score=item.freshness_score,
                quality_score=item.quality_score,
                metrics=item.metrics,
                warnings=item.warnings,
                provenance=item.provenance,
            )
            for item in evidence
        ]

        result = AnalysisResult(
            analysis_id=analysis.id,
            title_id=title.id,
            market_potential_score=market_score,
            decision_classification=classification,
            confidence_score=confidence,
            confidence_level=confidence_level,
            confidence_interval=interval,
            component_scores=component_scores,
            regional_scores=regions,
            comparable_titles=comparables,
            positive_drivers=positive,
            negative_drivers=negative,
            source_status=source_status,
            data_quality_warnings=warnings,
            recommendation=recommendation,
            model_version=analysis.model_version,
            feature_version=analysis.feature_version,
            scoring_version=analysis.scoring_version,
            score_origin=score_origin,
            score_meaning=score_meaning,
            model_warnings=model_warnings,
            component_details=component_details,
            model_evaluation=model_evaluation,
        )

        analysis.result = result.model_dump(mode="json")
        analysis.warnings = warnings
        analysis.status = (
            "partially_completed"
            if any(item.status == "unavailable" for item in evidence)
            else "completed"
        )
        analysis.completed_at = utcnow()
        job.status = analysis.status
        job.progress = 100
        job.stage = "analysis completed"
        job.updated_at = utcnow()
        db.commit()
    except Exception:
        db.rollback()
        analysis = db.get(Analysis, analysis_id)
        if analysis is not None:
            analysis.status = "failed"
            analysis.error_message = PUBLIC_FAILURE_MESSAGE
            if analysis.job is not None:
                analysis.job.status = "failed"
                analysis.job.stage = "analysis failed"
                analysis.job.error_message = PUBLIC_FAILURE_MESSAGE
                analysis.job.updated_at = utcnow()
            db.commit()
        logger.exception("analysis_failed")
    finally:
        db.close()


def create_analysis(db: Session, title: Title) -> tuple[Analysis, Job]:
    analysis = Analysis(
        title_id=title.id,
        status="queued",
        model_version=settings.model_version,
        feature_version=settings.feature_version,
        scoring_version=settings.scoring_version,
    )
    db.add(analysis)
    db.flush()
    job = Job(analysis_id=analysis.id, status="queued", progress=0, stage="queued")
    db.add(job)
    db.commit()
    db.refresh(analysis)
    db.refresh(job)
    return analysis, job
