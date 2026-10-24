import csv
import io
import re

import pytest

from kizuna import engine, report
from kizuna.api import MockApi

TITLES = ["shadow_bloom", "hollow_tide", "kitsune_circuit"]


def ctx_for(tid, approval=True, title_override=None):
    api = MockApi(stage_seconds=0)
    cfg = api.get_config()
    analysis, sources, comps = api.get_analysis(tid), api.get_sources(tid), api.get_comparables(tid)
    view = engine.compute_view(analysis, sources, comps, cfg)
    title = api.get_title(tid)
    if title_override:
        title["title"] = title_override
    data = {
        "title": title,
        "analysis": analysis,
        "sources": sources,
        "comparables": comps,
        "view": view,
        "regions": engine.rank_regions(api.get_regions(tid)["regions"], cfg),
        "cfg": cfg,
        "reco": api.get_recommendation(tid),
        "scenarios": api.get_scenarios(tid),
        "language_affinity": api.get_regions(tid)["language_affinity"],
    }
    results = engine.scenario_results(view, data["scenarios"], cfg)
    rec = engine.recommend_scenario(results[1:], cfg)
    appr = (
        {"status": "accepted", "by": "Tester", "reason": "", "time": "2026-10-24 10:00:00"}
        if approval
        else None
    )
    return report.make_context(data, results, rec, appr, [])


def pages(pdf):
    return len(re.findall(rb"/Type /Page\b(?!s)", pdf))


@pytest.mark.parametrize("tid", TITLES)
def test_pdfs_build_for_every_title(tid):
    ctx = ctx_for(tid)
    brief, full = report.executive_brief_pdf(ctx), report.full_report_pdf(ctx)
    assert brief.startswith(b"%PDF") and full.startswith(b"%PDF")
    assert pages(brief) == 1
    assert pages(full) >= 2


def test_pdf_survives_japanese_and_markup_in_title():
    ctx = ctx_for("shadow_bloom", title_override="<script>alert(1)</script> シャドウ — test")
    assert report.executive_brief_pdf(ctx).startswith(b"%PDF")
    assert report.full_report_pdf(ctx).startswith(b"%PDF")


def test_sanitize_replaces_non_latin1_and_normalizes_punctuation():
    assert report.sanitize("シ a — b") == "? a - b"
    assert report.sanitize(None) == ""


def test_regional_csv_has_all_regions_and_no_delhi_ncr():
    ctx = ctx_for("shadow_bloom")
    rows = list(csv.DictReader(io.StringIO(report.regional_csv(ctx).decode())))
    assert len(rows) == 36
    assert any(r["state"] == "Delhi" for r in rows)
    assert not any("ncr" in r["state"].lower() for r in rows)
    assert {r["not_ranked"] for r in rows} == {"yes", "no"}


def test_scenario_csv_rows():
    ctx = ctx_for("shadow_bloom")
    rows = list(csv.DictReader(io.StringIO(report.scenario_csv(ctx).decode())))
    assert [r["scenario"] for r in rows][0] == "Base strategy" and len(rows) == 3


def test_map_html_is_self_contained():
    html = report.map_html(ctx_for("shadow_bloom")).decode()
    assert "<html" in html and "Plotly" in html
    assert '<script src="https://' not in html and "<script src='https://" not in html
