"""Download formats for one saved analysis (the dashboard's Decision page): PDF, JSON, CSV and XML.

`build_export` freezes the title record and the analysis result into one dict; every renderer reads
only that dict, so the four files always agree. (`build.py` does the same for the /predict report.)
"""

import csv
import io
import re
from datetime import UTC, datetime

from app.db.models import Analysis, Title
from app.reports.analysis_pdf import to_pdf
from app.reports.text_formats import to_json, to_xml
from app.schemas.analysis import AnalysisResult
from app.schemas.project import TitleRead, utc_iso

EXPORT_VERSION = "analysis-report-v1"

MEDIA = {
    "pdf": "application/pdf",
    "json": "application/json",
    "csv": "text/csv; charset=utf-8",
    "xml": "application/xml",
}

CSV_COLUMNS = [
    "title",
    "english_title",
    "market_potential_score",
    "decision",
    "confidence_score",
    "confidence_level",
    "range_low",
    "range_high",
    "score_origin",
    "model_version",
    "rank",
    "state",
    "region_score",
    "region_confidence",
    "recommended_language",
    "preferred_platform",
    "reasons",
]


def build_export(title: Title, analysis: Analysis) -> dict:
    """The title as saved plus the frozen result, with the versions that produced it."""
    result = AnalysisResult.model_validate(analysis.result)
    return {
        "report_version": EXPORT_VERSION,
        "generated_at": utc_iso(datetime.now(UTC)),
        "analysis": {
            "id": analysis.id,
            "status": analysis.status,
            "created_at": utc_iso(analysis.created_at),
            "completed_at": utc_iso(analysis.completed_at) if analysis.completed_at else None,
            "model_version": analysis.model_version,
            "feature_version": analysis.feature_version,
            "scoring_version": analysis.scoring_version,
        },
        "title": TitleRead.model_validate(title).model_dump(mode="json"),
        "result": result.model_dump(mode="json"),
    }


def to_csv(report: dict) -> bytes:
    """One row per scored region; the title-level numbers repeat so the file stands alone in a spreadsheet."""
    t, r = report["title"], report["result"]
    low, high = r["confidence_interval"]
    head = {
        "title": t["name"],
        "english_title": t["english_title"],
        "market_potential_score": round(r["market_potential_score"], 2),
        "decision": r["decision_classification"],
        "confidence_score": round(r["confidence_score"], 2),
        "confidence_level": r["confidence_level"],
        "range_low": round(low, 2),
        "range_high": round(high, 2),
        "score_origin": r["score_origin"],
        "model_version": r["model_version"],
    }
    buf = io.StringIO()
    writer = csv.DictWriter(buf, CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    ranked = sorted(r["regional_scores"], key=lambda region: -region["score"])
    for rank, region in enumerate(ranked, start=1):
        writer.writerow(
            head
            | {
                "rank": rank,
                "state": region["state"],
                "region_score": round(region["score"], 2),
                "region_confidence": round(region["confidence"], 2),
                "recommended_language": region["recommended_language"],
                "preferred_platform": region["preferred_platform"],
                "reasons": "; ".join(region["reasons"]),
            }
        )
    return ("﻿" + buf.getvalue()).encode("utf-8")  # BOM so Excel reads Japanese titles correctly


RENDER = {"json": to_json, "csv": to_csv, "xml": to_xml, "pdf": to_pdf}


def filename(report: dict, fmt: str) -> str:
    """ASCII-safe download name: the English title if there is one, else the analysis id."""
    t = report["title"]
    slug = re.sub(r"[^a-z0-9]+", "-", (t["english_title"] or "").lower()).strip("-")
    return f"kizuna-{slug or report['analysis']['id'][:8]}-analysis.{fmt}"
