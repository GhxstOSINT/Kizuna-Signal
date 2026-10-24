"""Results tab: comparable titles with include/exclude controls and live deltas."""
import streamlit as st

from kizuna import state, theme
from kizuna.theme import esc, html

SET_LABELS = {"expected": "Expected", "optimistic": "Optimistic", "conservative": "Conservative"}
LEVEL_KIND = {"High": "good", "Strong": "good", "Exact": "good", "Medium": "info", "Moderate": "info",
              "Low": "bad", "Weak": "bad"}


def _current_ids(data, tid):
    inc = state.get_overrides(tid)["included_comps"]
    return list(inc) if inc is not None else list(data["comparables"]["sets"]["expected"])


def _current_set(data, ids):
    for name, members in data["comparables"]["sets"].items():
        if set(members) == set(ids):
            return name
    return "custom"


def _switch_set(data, tid):
    name = st.session_state[f"compset_{tid}"]
    if name in data["comparables"]["sets"]:
        state.set_included_comps(tid, data["comparables"]["sets"][name], reason=f"Switched to {name} set")


def _toggle(tid, cid, include, current, minimum, title):
    ids = list(current)
    if include and cid not in ids:
        ids.append(cid)
    elif not include and cid in ids:
        if len(ids) <= minimum:
            return
        ids.remove(cid)
    state.set_included_comps(tid, ids, reason=f"{'Included' if include else 'Excluded'} {title}")


def _card(c, tid, included, current, minimum):
    with st.container(border=True):
        html(f'<div class="kz-title">{esc(c["title"])}</div>'
             f'<div class="kz-sub">{c["year"]} &middot; {esc(c["format"])}</div>'
             f'<div class="kz-big" style="font-size:1.8rem; margin:6px 0;">{c["similarity"] * 100:.0f}%'
             f'<small> similarity</small></div>'
             + theme.meter(c["similarity"] * 100)
             + theme.row("Indian demand", c["indian_demand"])
             + theme.row("India performance", c["india_performance"]))
        html(" ".join([theme.badge(f"Genre: {c['genre_match']}", LEVEL_KIND.get(c["genre_match"], "neutral")),
                       theme.badge(f"Audience: {c['audience_match']}", LEVEL_KIND.get(c["audience_match"], "neutral")),
                       theme.badge(f"Format: {c['format_match']}", LEVEL_KIND.get(c["format_match"], "neutral"))]))
        st.caption(f"Why it was selected: {c['reason']}")
        if included:
            blocked = len(current) <= minimum
            st.button("Exclude", key=f"exc_{tid}_{c['id']}", use_container_width=True, disabled=blocked,
                      help=f"At least {minimum} comparables must stay included." if blocked else None,
                      on_click=_toggle, args=(tid, c["id"], False, current, minimum, c["title"]))
        else:
            st.button("Include", key=f"inc_{tid}_{c['id']}", use_container_width=True, type="primary",
                      on_click=_toggle, args=(tid, c["id"], True, current, minimum, c["title"]))


def render(data, tid):
    view, cfg = data["view"], data["cfg"]
    minimum = cfg["min_comparables"]
    ids = _current_ids(data, tid)
    sets = data["comparables"]["sets"]
    st.subheader("Comparable titles")
    st.caption("Retrieved by semantic similarity, then re-ranked by genre, audience, format and Indian evidence. "
               "Every inclusion or exclusion is recorded in the audit log.")

    current = _current_set(data, ids)
    options = list(SET_LABELS) + (["custom"] if current == "custom" else [])
    st.session_state[f"compset_{tid}"] = current
    st.radio("Comparable set", options, format_func=lambda k: SET_LABELS.get(k, "Custom selection"),
             horizontal=True, key=f"compset_{tid}", on_change=_switch_set, args=(data, tid))

    base = view["base"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Comparable Performance", f"{view['components']['comparable_performance']:.0f}")
    m2.metric("Market potential", view["overall"], f"{view['delta_score']:+d} vs base" if view["delta_score"] else None)
    m3.metric("Confidence", f"{view['confidence']}%",
              f"{view['delta_confidence']:+d} vs base" if view["delta_confidence"] else None)

    by_id = {c["id"]: c for c in data["comparables"]["comparables"]}
    inc_cards = sorted((by_id[i] for i in ids), key=lambda c: -c["similarity"])
    others = sorted((c for i, c in by_id.items() if i not in ids), key=lambda c: -c["similarity"])

    st.markdown(f"#### Included in the analysis ({len(inc_cards)})")
    cols = st.columns(3)
    for n, c in enumerate(inc_cards):
        with cols[n % 3]:
            _card(c, tid, True, ids, minimum)
    if others:
        st.markdown(f"#### Candidates not included ({len(others)})")
        cols = st.columns(3)
        for n, c in enumerate(others):
            with cols[n % 3]:
                _card(c, tid, False, ids, minimum)
    if state.has_overrides(tid):
        if st.button("Reset all overrides to base", key=f"reset_{tid}_comp"):
            state.reset_overrides(tid)
            st.rerun()
