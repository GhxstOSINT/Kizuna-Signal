"""JSON, CSV and XML renderers for the report dict."""

import csv
import io
import json
import re
import xml.etree.ElementTree as ET

CSV_COLUMNS = [
    "title",
    "success_rating",
    "success_score",
    "success_low",
    "success_high",
    "success_band",
    "success_coverage",
    "confidence",
    "state_code",
    "state_name",
    "rank",
    "lift",
    "lift_low",
    "lift_high",
    "expected_share",
    "train_titles",
    "top_drivers",
]
# repeated-element names for lists in the XML output
SINGULAR = {
    "states": "state",
    "components": "component",
    "comparables": "comparable",
    "formulas": "formula",
    "warnings": "warning",
    "limitations": "limitation",
    "drivers": "driver",
    "genres": "genre",
    "tags": "tag",
    "top_states": "state",
    "bottom_states": "state",
    "candidates": "candidate",
    # analysis export (analysis_export.py)
    "themes": "theme",
    "target_languages": "language",
    "target_states": "state",
    "regional_scores": "region",
    "comparable_titles": "comparable",
    "positive_drivers": "driver",
    "negative_drivers": "driver",
    "source_status": "source",
    "data_quality_warnings": "warning",
    "model_warnings": "warning",
    "component_details": "component",
    "reasons": "reason",
    "priority_markets": "market",
    "campaign_actions": "action",
    "risks": "risk",
    "confidence_interval": "bound",
}


def to_json(report: dict) -> bytes:
    return json.dumps(report, indent=2, ensure_ascii=False, default=str).encode("utf-8")


def to_csv(report: dict) -> bytes:
    """One row per state. Title-level scores repeat on every row so the file stands alone in a spreadsheet."""
    s = report["success"] or {}
    head = {
        "title": report["title"]["name_en"],
        "success_rating": s.get("rating"),
        "success_score": s.get("score"),
        "success_low": s.get("low"),
        "success_high": s.get("high"),
        "success_band": s.get("band"),
        "success_coverage": s.get("coverage"),
        "confidence": report["india"]["confidence"],
    }
    buf = io.StringIO()
    w = csv.DictWriter(buf, CSV_COLUMNS, lineterminator="\n")
    w.writeheader()
    for st in report["states"]:
        w.writerow(
            head
            | {
                "state_code": st["state"],
                "state_name": st["name"],
                "rank": st["rank"],
                "lift": round(st["lift"], 4),
                "lift_low": round(st["low"], 4),
                "lift_high": round(st["high"], 4),
                "expected_share": round(st["expected_share"], 5),
                "train_titles": st["train_titles"],
                "top_drivers": "; ".join(
                    f"{d['feature']}={d['contribution']:+.4f}" for d in st["drivers"]
                ),
            }
        )
    return ("﻿" + buf.getvalue()).encode("utf-8")  # BOM so Excel reads Japanese titles correctly


def _tag(name: str) -> str:
    tag = re.sub(r"[^A-Za-z0-9_.-]", "_", str(name))
    return tag if re.match(r"[A-Za-z_]", tag) else f"_{tag}"


def _add(parent: ET.Element, name: str, value) -> None:
    if value is None:
        return
    el = ET.SubElement(parent, _tag(name))
    if isinstance(value, dict):
        for k, v in value.items():
            _add(el, k, v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _add(el, SINGULAR.get(name, "item"), v)
    elif isinstance(value, bool):
        el.text = "true" if value else "false"
    elif isinstance(value, float):
        el.text = f"{value:.6g}"
    else:
        el.text = str(value)


def to_xml(report: dict) -> bytes:
    root = ET.Element("kizunaReport", version=report["report_version"])
    for key, value in report.items():
        if key != "report_version":
            _add(root, key, value)
    ET.indent(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
