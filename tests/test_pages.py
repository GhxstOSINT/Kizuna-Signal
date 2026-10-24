"""Smoke tests: every page renders for every seed title without an exception."""
import pytest
from streamlit.testing.v1 import AppTest

TITLES = ["shadow_bloom", "hollow_tide", "kitsune_circuit"]


def _script(module_name, title_id):
    import importlib

    import streamlit as st

    st.session_state.setdefault("active_title", title_id)
    importlib.import_module(module_name).render()


def run_page(module_name, title_id="shadow_bloom", setup=None):
    at = AppTest.from_function(_script, args=(module_name, title_id), default_timeout=60)
    if setup:
        setup(at)
    return at.run()


@pytest.mark.parametrize("tid", TITLES)
def test_portfolio_renders(tid):
    at = run_page("views.portfolio", tid)
    assert not at.exception
    assert [t.value for t in at.title] == ["Portfolio"]
    assert len([b for b in at.button if b.label == "Open results"]) == 3


@pytest.mark.parametrize("tid", TITLES)
def test_results_renders(tid):
    at = run_page("views.results", tid)
    assert not at.exception
    assert len(at.tabs) == 5


def test_low_confidence_title_shows_warning_message():
    at = run_page("views.results", "hollow_tide")
    text = " ".join(m.value for m in at.markdown)
    assert "More evidence is required" in text
    assert "Insufficient evidence" in text


def test_partial_title_shows_partial_message():
    at = run_page("views.results", "kitsune_circuit")
    text = " ".join(m.value for m in at.markdown)
    assert "limited evidence" in text.lower()


def test_exclude_comparable_updates_score_and_logs():
    at = run_page("views.results", "shadow_bloom")
    btn = next(b for b in at.button if b.key == "exc_shadow_bloom_chainsaw_man")
    btn.click()
    at.run()
    assert not at.exception
    ov = at.session_state["overrides"]["shadow_bloom"]
    assert "chainsaw_man" not in ov["included_comps"] and len(ov["included_comps"]) == 4
    assert at.session_state["audit_log"][-1]["action"] == "comparables_changed"


def test_cannot_exclude_below_minimum_comparables():
    at = run_page("views.results", "shadow_bloom")
    for cid in ["chainsaw_man", "frieren", "solo_leveling"]:
        next(b for b in at.button if b.key == f"exc_shadow_bloom_{cid}").click()
        at.run()
    ov = at.session_state["overrides"]["shadow_bloom"]
    assert len(ov["included_comps"]) == 2
    assert all(b.disabled for b in at.button if b.key and b.key.startswith("exc_shadow_bloom_"))


def test_disable_source_recalculates_and_reenable_restores():
    at = run_page("views.results", "shadow_bloom")
    tg = next(t for t in at.toggle if t.key == "src_shadow_bloom_google_trends")
    tg.set_value(False)
    at.run()
    assert not at.exception
    assert at.session_state["overrides"]["shadow_bloom"]["disabled_sources"] == ["google_trends"]
    tg = next(t for t in at.toggle if t.key == "src_shadow_bloom_google_trends")
    tg.set_value(True)
    at.run()
    assert at.session_state["overrides"]["shadow_bloom"]["disabled_sources"] == []


def _fill_required(at):
    at.text_input(key="na_title").set_value("Test <b>Title</b> テスト")
    at.text_area(key="na_synopsis").set_value("A synopsis with <script>alert(1)</script>.")
    at.selectbox(key="na_format").select("Anime series")
    at.selectbox(key="na_primary_genre").select("Fantasy")
    at.selectbox(key="na_source_material").select("Original")
    at.text_input(key="na_release_period").set_value("March 2027")
    at.selectbox(key="na_target_platform").select("OTT")


def test_new_analysis_blocks_submit_until_required_fields_filled():
    at = run_page("views.new_analysis")
    assert not at.exception
    run = next(b for b in at.button if b.label == "Run Market Analysis")
    assert run.disabled
    _fill_required(at)
    at.run()
    run = next(b for b in at.button if b.label == "Run Market Analysis")
    assert not run.disabled


def test_new_analysis_submit_starts_job():
    at = run_page("views.new_analysis")
    _fill_required(at)
    at.run()
    next(b for b in at.button if b.label == "Run Market Analysis").click()
    at.run()
    assert not at.exception
    assert at.session_state["na_job"] == "job_1"


def _submit(outcome_label):
    from kizuna.api import MockApi

    at = run_page("views.new_analysis", setup=lambda a: a.session_state.__setitem__("api", MockApi(stage_seconds=0)))
    _fill_required(at)
    at.radio(key="na_outcome").set_value(outcome_label)
    at.run()
    next(b for b in at.button if b.label == "Run Market Analysis").click()
    return at.run()


def test_failure_outcome_shows_error_state_with_retry_and_cached_actions():
    at = _submit("Failure (AniList timeout)")
    assert not at.exception
    assert any("could not be completed" in e.value for e in at.error)
    labels = [b.label for b in at.button]
    assert "Retry" in labels and "Use Cached Data" in labels


def test_retry_after_failure_completes_and_creates_project():
    at = _submit("Failure (AniList timeout)")
    next(b for b in at.button if b.label == "Retry").click()
    at.run()
    assert not at.exception
    assert any(p["custom"] for p in at.session_state["api"].list_projects())
    assert at.session_state["active_title"].startswith("custom_")


def test_use_cached_data_after_failure_gives_partial_result():
    at = _submit("Failure (AniList timeout)")
    next(b for b in at.button if b.label == "Use Cached Data").click()
    at.run()
    assert not at.exception
    tid = at.session_state["active_title"]
    assert at.session_state["api"].get_analysis(tid)["status"] == "partial"


def test_partial_outcome_result_renders_with_partial_notice():
    at = _submit("Partial data (YouTube unavailable)")
    assert not at.exception
    tid = at.session_state["active_title"]
    res = run_page("views.results", tid,
                   setup=lambda a: a.session_state.__setitem__("api", at.session_state["api"]))
    assert not res.exception
    assert "limited evidence" in " ".join(m.value for m in res.markdown).lower()


@pytest.mark.parametrize("tid", TITLES)
def test_scenario_lab_renders(tid):
    at = run_page("views.scenario_lab", tid)
    assert not at.exception
    assert [t.value for t in at.title][0].startswith("Scenario Lab")


def test_scenario_lab_custom_scenario_adds_column_and_keeps_base_unchanged():
    at = run_page("views.scenario_lab", "shadow_bloom")
    at.selectbox(key="lever_shadow_bloom_marketing_budget").select("high")
    at.run()
    assert not at.exception
    names = [m.value for m in at.markdown if m.value.startswith("**")]
    assert "**Custom scenario**" in names
    assert not at.session_state["overrides"]["shadow_bloom"]["disabled_sources"]
    assert "78" in " ".join(str(m.value) for m in at.metric)
