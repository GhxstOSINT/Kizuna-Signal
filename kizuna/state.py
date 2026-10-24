"""Session-state helpers: API client, overrides, approvals and the audit log."""
from datetime import datetime

import streamlit as st

from . import engine
from .api import MockApi


def get_api():
    if "api" not in st.session_state:
        st.session_state["api"] = MockApi()
    return st.session_state["api"]


def get_cfg():
    if "cfg" not in st.session_state:
        st.session_state["cfg"] = get_api().get_config()
    return st.session_state["cfg"]


# ------------------------------------------------------------ navigation
def register_pages(pages):
    st.session_state["_pages"] = pages


def goto(name):
    page = st.session_state.get("_pages", {}).get(name)
    if page is not None:
        st.switch_page(page)


# ---------------------------------------------------------- active title
def active_title():
    projects = get_api().list_projects()
    ids = [p["title_id"] for p in projects]
    cur = st.session_state.get("active_title")
    if cur not in ids:
        cur = ids[0] if ids else None
        st.session_state["active_title"] = cur
    return cur


def set_active_title(title_id):
    st.session_state["active_title"] = title_id


def show_optional():
    return bool(st.session_state.get("show_optional", False))


def analyst_name():
    return (st.session_state.get("analyst_name") or "Analyst").strip() or "Analyst"


# ------------------------------------------------------------- overrides
def get_overrides(title_id):
    store = st.session_state.setdefault("overrides", {})
    return store.setdefault(title_id, {"disabled_sources": [], "included_comps": None})


def log(action, title_id, previous, new, reason=""):
    st.session_state.setdefault("audit_log", []).append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "user": analyst_name(),
        "title_id": title_id, "action": action, "previous": str(previous), "new": str(new), "reason": reason,
    })


def audit_log():
    return list(st.session_state.get("audit_log", []))


def set_source_enabled(title_id, source_id, enabled):
    ov = get_overrides(title_id)
    disabled = list(ov["disabled_sources"])
    if enabled and source_id in disabled:
        disabled.remove(source_id)
    elif not enabled and source_id not in disabled:
        disabled.append(source_id)
    else:
        return
    log("source_toggle", title_id, "disabled" if enabled else "enabled",
        "enabled" if enabled else "disabled", reason=source_id)
    ov["disabled_sources"] = disabled
    reset_approval(title_id, "Inputs changed after approval.")


def set_included_comps(title_id, ids, reason=""):
    ov = get_overrides(title_id)
    prev = ov["included_comps"]
    if prev is not None and list(prev) == list(ids):
        return
    log("comparables_changed", title_id, prev if prev is not None else "default set", list(ids), reason)
    ov["included_comps"] = list(ids)
    reset_approval(title_id, "Inputs changed after approval.")


def reset_overrides(title_id):
    st.session_state.setdefault("overrides", {})[title_id] = {"disabled_sources": [], "included_comps": None}
    log("overrides_reset", title_id, "custom", "base", "")
    reset_approval(title_id, "Inputs changed after approval.")


# -------------------------------------------------------------- approvals
def get_approval(title_id):
    return st.session_state.setdefault("approvals", {}).get(title_id)


def set_approval(title_id, status, name, reason=""):
    st.session_state.setdefault("approvals", {})[title_id] = {
        "status": status, "by": name, "reason": reason,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    log(f"recommendation_{status}", title_id, "proposed", status, reason)


def reset_approval(title_id, why):
    approvals = st.session_state.setdefault("approvals", {})
    if title_id in approvals:
        del approvals[title_id]
        log("approval_reset", title_id, "accepted", "proposed", why)


# ------------------------------------------------------------ data loader
def load(title_id):
    """Everything a page needs for one title, with analyst overrides applied."""
    api, cfg = get_api(), get_cfg()
    analysis = api.get_analysis(title_id)
    sources = api.get_sources(title_id)
    comparables = api.get_comparables(title_id)
    view = engine.compute_view(analysis, sources, comparables, cfg, get_overrides(title_id),
                               include_optional=show_optional())
    regions = engine.rank_regions(api.get_regions(title_id)["regions"], cfg)
    return {"title": api.get_title(title_id), "analysis": analysis, "sources": sources,
            "comparables": comparables, "view": view, "regions": regions, "cfg": cfg}
