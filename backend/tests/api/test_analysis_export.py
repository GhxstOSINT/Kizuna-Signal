"""GET /analyses/{id}/export: the Decision page as PDF, JSON, CSV and XML."""

from __future__ import annotations

import copy
import csv
import io
import json
import re
import xml.etree.ElementTree as ET

import pytest

from app.db.models import Analysis
from app.db.session import SessionLocal
from app.reports import analysis_export, analysis_pdf


@pytest.fixture
def analysis_id(client, title_payload):
    project = client.post("/api/v1/projects", json={"name": "Export"}).json()
    title = client.post(f"/api/v1/projects/{project['id']}/titles", json=title_payload).json()
    return client.post(f"/api/v1/titles/{title['id']}/analyses", json={}).json()["analysis_id"]


def page_count(pdf: bytes) -> int:
    return len(re.findall(rb"/Type /Page /Parent", pdf))


def export(client, analysis_id, fmt):
    return client.get(f"/api/v1/analyses/{analysis_id}/export", params={"format": fmt})


@pytest.mark.api
def test_pdf_is_the_default_and_downloads_as_a_file(client, analysis_id):
    r = client.get(f"/api/v1/analyses/{analysis_id}/export")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert (
        r.headers["content-disposition"]
        == 'attachment; filename="kizuna-shadow-bloom-analysis.pdf"'
    )
    assert r.content.startswith(b"%PDF")
    assert page_count(r.content) >= 3  # a multi-page report, not a stub


@pytest.mark.api
def test_json_holds_the_title_and_the_frozen_result(client, analysis_id):
    r = export(client, analysis_id, "json")
    body = r.json()
    stored = client.get(f"/api/v1/analyses/{analysis_id}/result").json()
    assert r.headers["content-type"] == "application/json"
    assert body["report_version"] == analysis_export.EXPORT_VERSION
    assert body["analysis"]["id"] == analysis_id
    assert body["title"]["name"] == "Shadow Bloom"
    assert body["result"] == stored


@pytest.mark.api
def test_csv_has_one_row_per_region_best_first(client, analysis_id):
    r = export(client, analysis_id, "csv")
    rows = list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
    regions = client.get(f"/api/v1/analyses/{analysis_id}/result").json()["regional_scores"]
    assert r.headers["content-type"].startswith("text/csv")
    assert r.content.startswith("﻿".encode())  # BOM for Excel
    assert len(rows) == len(regions)
    assert [int(row["rank"]) for row in rows] == list(range(1, len(rows) + 1))
    scores = [float(row["region_score"]) for row in rows]
    assert scores == sorted(scores, reverse=True)
    assert {row["title"] for row in rows} == {"Shadow Bloom"}


@pytest.mark.api
def test_xml_is_well_formed_with_named_list_items(client, analysis_id):
    r = export(client, analysis_id, "xml")
    root = ET.fromstring(r.content)
    assert r.headers["content-type"] == "application/xml"
    assert root.tag == "kizunaReport"
    assert root.get("version") == analysis_export.EXPORT_VERSION
    assert root.find("title/name").text == "Shadow Bloom"
    assert len(root.findall("result/regional_scores/region")) > 0
    assert [e.tag for e in root.find("result/confidence_interval")] == ["bound", "bound"]


@pytest.mark.api
def test_unknown_format_is_rejected(client, analysis_id):
    assert export(client, analysis_id, "docx").status_code == 422


@pytest.mark.api
def test_unfinished_analysis_has_nothing_to_export(client, analysis_id):
    with SessionLocal() as db:
        analysis = db.get(Analysis, analysis_id)
        analysis.result, analysis.status = None, "running"
        db.commit()
    r = export(client, analysis_id, "pdf")
    assert r.status_code == 409
    assert "running" in r.json()["error"]["message"]


@pytest.mark.security
def test_export_needs_a_session_and_ownership(client, other_client, anonymous_client, analysis_id):
    for fmt in ("pdf", "json", "csv", "xml"):
        assert export(other_client, analysis_id, fmt).status_code == 404
        assert export(anonymous_client, analysis_id, fmt).status_code == 401


@pytest.mark.unit
def test_file_name_falls_back_to_the_analysis_id_without_an_english_title():
    report = {"title": {"english_title": None}, "analysis": {"id": "5b18fa68-6bc9"}}
    assert analysis_export.filename(report, "csv") == "kizuna-5b18fa68-analysis.csv"


# ---------------------------------------------------------------------------- PDF layout branches
@pytest.fixture
def report(client, analysis_id):
    return export(client, analysis_id, "json").json()


@pytest.mark.unit
def test_pdf_handles_a_fallback_score_with_no_notes_or_regions(report):
    report = copy.deepcopy(report)
    r = report["result"]
    r.update(
        score_origin="deterministic_fallback",
        data_quality_warnings=[],
        regional_scores=[],
        negative_drivers=[],
        component_details=[],
    )
    report["title"].update(english_title=None, studio=None, episode_count=12, age_rating="13_plus")
    assert analysis_pdf.to_pdf(report).startswith(b"%PDF")


@pytest.mark.unit
def test_pdf_flows_long_content_over_several_pages(report):
    report = copy.deepcopy(report)
    r = report["result"]
    r["data_quality_warnings"] = [f"Evidence note {i}: " + "long words " * 40 for i in range(30)]
    r["comparable_titles"] = r["comparable_titles"] * 8
    r["positive_drivers"] = r["positive_drivers"] * 10
    r["source_status"] = r["source_status"] * 4
    report["title"]["synopsis"] = "x" * 3000
    report["title"]["name"] = "unbroken" * 30  # a single word wider than the column
    pdf = analysis_pdf.to_pdf(report)
    assert page_count(pdf) > 8


@pytest.mark.unit
def test_pdf_embeds_type3_fonts_when_truetype_embedding_fails(report, monkeypatch):
    calls = []
    real = analysis_pdf._render

    def flaky(rep, fonttype):
        calls.append(fonttype)
        if fonttype == 42:
            raise RuntimeError("font cannot be embedded")
        return real(rep, fonttype)

    monkeypatch.setattr(analysis_pdf, "_render", flaky)
    assert analysis_pdf.to_pdf(report).startswith(b"%PDF")
    assert calls == [42, 3]


@pytest.mark.unit
def test_exports_serialise_without_the_database(report):
    assert (
        json.loads(analysis_export.RENDER["json"](report))["analysis"]["id"]
        == report["analysis"]["id"]
    )
