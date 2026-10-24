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
