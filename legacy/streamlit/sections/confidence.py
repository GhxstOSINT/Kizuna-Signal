"""Results tab: confidence factors, warnings and source health with toggles."""
from datetime import datetime

import streamlit as st

from kizuna import state, theme
from kizuna.theme import esc, html

PUBLIC_SOURCES = ("anilist", "google_trends", "youtube", "wikimedia", "census")
SEVERITY_KIND = {"critical": "bad", "warning": "warn", "info": "info"}
STATUS_KIND = {"available": "good", "unavailable": "bad", "not_connected": "neutral"}


def fmt_time(ts):
    if not ts:
        return "-"
    try:
        return datetime.fromisoformat(ts).strftime("%d %b %Y, %H:%M")
    except ValueError:
        return ts


def public_availability(sources):
    pub = [s for s in sources if s["id"] in PUBLIC_SOURCES]
    return sum(s["status"] == "available" for s in pub), len(pub)


def warnings(data):
    """Analysis warnings plus the ones caused by current analyst overrides and data state."""
    view, analysis, sources = data["view"], data["analysis"], data["sources"]
    out = [(w["severity"], w["message"]) for w in analysis["warnings"]]
    names = {s["id"]: s["name"] for s in sources}
    for sid in view["disabled_sources"]:
        out.append(("info", f"{names.get(sid, sid)} is disabled by the analyst; confidence was recalculated."))
    n_supp = len(data["regions"]["suppressed"])
    if n_supp:
        out.append(("info", f"{n_supp} regions have insufficient evidence and are not ranked."))
    if analysis.get("model_used") != "primary":
        out.append(("warning", "Baseline model fallback was used; uncertainty is wider."))
    for s in sources:
        if s["status"] == "available" and s["mode"] == "cached" and s["id"] in PUBLIC_SOURCES:
            out.append(("info", f"{s['name']}: cached data used. {s['note']}".strip()))
    return out


def render_warnings(data):
    for sev, msg in warnings(data):
        html(theme.note(msg, SEVERITY_KIND.get(sev, "warn")))
        html('<div style="height:6px"></div>')


def _toggle_changed(tid, sid):
    state.set_source_enabled(tid, sid, st.session_state[f"src_{tid}_{sid}"])


def render(data, tid):
    view, sources = data["view"], data["sources"]
    base = view["base"]

    st.subheader("Confidence and data quality")
    st.caption("Confidence measures evidence quality, not market potential. They are always shown separately.")
    left, right = st.columns([3, 2])
    with left:
        c1, c2 = st.columns(2)
        c1.metric("Prediction confidence", f"{view['confidence']}%", f"{view['delta_confidence']:+d} vs base"
                  if view["delta_confidence"] else None)
        c2.metric("Expected range", f"{view['interval'][0]}-{view['interval'][1]}")
        for f in data["cfg"]["confidence_factors"]:
            val = view["factors"][f["id"]]
            delta = val - data["analysis"]["confidence_factors"][f["id"]]
            tail = f" ({delta:+.0f})" if abs(delta) >= 0.5 else ""
            html(f'<div class="kz-row"><span>{esc(f["label"])}</span><span>{val:.0f}%{tail}</span></div>'
                 + theme.meter(val, theme.GOOD if val >= 75 else theme.PRIMARY if val >= 55 else theme.WARN))
    with right:
        st.markdown("**Attention required**")
        render_warnings(data)

    st.divider()
    st.subheader("Source health and controls")
    n_ok, n_all = public_availability(sources)
    st.caption(f"{n_ok} of {n_all} public sources available. Disable a noisy source to see how the score "
               "and confidence change. Unavailable sources cannot be re-enabled.")
    head = st.columns([2, 1.3, 1.2, 1.6, 3, 1])
    for col, text in zip(head, ["Source", "Status", "Mode", "Last collected", "Notes", "Use"]):
        col.markdown(f"<span class='kz-sub'>{text}</span>", unsafe_allow_html=True)
    for s in sources:
        c = st.columns([2, 1.3, 1.2, 1.6, 3, 1], vertical_alignment="center")
        c[0].markdown(f"**{esc(s['name'])}**")
        c[1].markdown(theme.badge(s["status"].replace("_", " ").capitalize(), STATUS_KIND.get(s["status"], "neutral")),
                      unsafe_allow_html=True)
        c[2].write(s["mode"].capitalize() if s["mode"] != "none" else "-")
        c[3].write(fmt_time(s["last_collected"]))
        c[4].markdown(f"<span class='kz-sub'>{esc(s['note'] or s['caveat'])}</span>", unsafe_allow_html=True)
        key = f"src_{tid}_{s['id']}"
        if s["toggleable"]:
            st.session_state[key] = s["id"] not in view["disabled_sources"]
            c[5].toggle("Use", key=key, label_visibility="collapsed", on_change=_toggle_changed, args=(tid, s["id"]))
        else:
            c[5].write("-")

    if state.has_overrides(tid):
        st.divider()
        cols = st.columns([4, 1], vertical_alignment="center")
        cols[0].info(f"Overrides active. Score {view['overall']} ({view['delta_score']:+d}), "
                     f"confidence {view['confidence']}% ({view['delta_confidence']:+d}) vs base "
                     f"{base['score']} / {base['confidence']}%.")
        if cols[1].button("Reset to base", key=f"reset_{tid}_conf", use_container_width=True):
            state.reset_overrides(tid)
            st.rerun()
