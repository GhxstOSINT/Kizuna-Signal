"""Results tab: executive decision header, component scores, content DNA, source coverage."""
import streamlit as st

from kizuna import charts, state, theme
from kizuna.theme import esc, html
from . import confidence


def _hero(data, tid):
    view, meta, analysis, reco = data["view"], data["title"], data["analysis"], data["reco"]
    lo, hi = view["interval"]
    with st.container(border=True):
        head = st.columns([5, 2], vertical_alignment="center")
        head[0].markdown(f"### {meta['title']}"
                         + (f" <span class='kz-sub'>{esc(meta['title_jp'])}</span>" if meta.get("title_jp") else ""),
                         unsafe_allow_html=True)
        badges = theme.badge(meta["format"])
        if analysis.get("model_used") != "primary":
            badges += " " + theme.badge("Baseline model", "warn")
        if analysis["status"] == "partial":
            badges += " " + theme.badge("Partial analysis", "warn")
        head[1].markdown(badges, unsafe_allow_html=True)

        c1, c2, c3 = st.columns([2, 2, 4])
        with c1:
            html(f'<div class="kz-label">India market potential</div>'
                 f'<div class="kz-big">{view["overall"]}<small> / 100</small></div>'
                 + theme.meter(view["overall"]) + theme.decision_badge(view["label"]))
        with c2:
            conf_kind = theme.confidence_kind(view["confidence"])
            html(f'<div class="kz-label">Confidence</div>'
                 f'<div class="kz-big">{view["confidence"]}<small> %</small></div>'
                 + theme.meter(view["confidence"], theme.GOOD if conf_kind == "good" else theme.WARN if conf_kind == "warn" else theme.BAD)
                 + theme.badge(f'{view["confidence_band"]} confidence', conf_kind)
                 + f'<div class="kz-sub" style="margin-top:6px;">Expected range {lo}-{hi}</div>')
        with c3:
            html('<div class="kz-label">Recommendation</div>')
            if view["low_confidence"]:
                html(theme.note(f"Potential score {view['overall']}, but confidence is only {view['confidence']}%. "
                                "More evidence is required before making a high-investment launch decision.", "bad"))
            html(f'<div class="kz-reco">{esc(data["reco"]["headline"])}</div>')


def _status_notes(data, tid):
    sources, analysis, view = data["sources"], data["analysis"], data["view"]
    if analysis.get("mock_notice"):
        html(theme.note(analysis["mock_notice"], "info"))
        html('<div style="height:6px"></div>')
    if analysis["status"] == "partial":
        n_ok, n_all = confidence.public_availability(sources)
        html(theme.note(f"Analysis completed with limited evidence. {n_ok} of {n_all} public sources were "
                        "available. Confidence has been adjusted accordingly."))
        html('<div style="height:6px"></div>')
    if state.has_overrides(tid):
        cols = st.columns([5, 1], vertical_alignment="center")
        cols[0].info(f"Analyst overrides active: score {view['overall']} ({view['delta_score']:+d}), "
                     f"confidence {view['confidence']}% ({view['delta_confidence']:+d}) vs base "
                     f"{view['base']['score']} / {view['base']['confidence']}%.")
        if cols[1].button("Reset to base", key=f"reset_{tid}_dec", use_container_width=True):
            state.reset_overrides(tid)
            st.rerun()


def _dna(data):
    dna, meta = data["analysis"]["content_dna"], data["title"]
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Title metadata**")
        rows = [("Format", meta["format"]), ("Genres", ", ".join(meta["genres"])),
                ("Source", meta["source_material"]), ("Studio", meta.get("studio") or "-"),
                ("Release", meta["release_period"]), ("Target platform", meta["target_platform"]),
                ("Age rating", meta.get("age_rating") or "-")]
        html("".join(theme.row(k, v) for k, v in rows))
        st.caption(meta["synopsis"])
    with c2:
        st.markdown("**Content DNA**")
        for group, key in (("Genres", "genres"), ("Themes", "themes")):
            st.caption(group)
            for item in dna[key]:
                html(theme.row(item["name"], f"{item['weight'] * 100:.0f}%") + theme.meter(item["weight"] * 100))
        st.caption("Archetypes")
        html(" ".join(theme.badge(a) for a in dna["archetypes"]))
        if dna["sensitivity_flags"]:
            st.caption("Sensitivity flags")
            for f in dna["sensitivity_flags"]:
                html(theme.note(f))
                html('<div style="height:4px"></div>')
    with c3:
        st.markdown("**Audience fit**")
        for k, v in dna["audience_fit"].items():
            html(theme.row(k, v) + theme.meter(v))


def _coverage(data):
    chips = []
    for s in data["sources"]:
        if s["id"] == "partner_csv":
            continue
        kind = confidence.STATUS_KIND.get(s["status"], "neutral")
        label = s["name"] + (" (cached)" if s["status"] == "available" and s["mode"] == "cached" else "")
        if s["status"] == "unavailable":
            label += " - unavailable"
        chips.append(theme.badge(label, kind))
    html(" ".join(chips))


def render(data, tid):
    _status_notes(data, tid)
    _hero(data, tid)
    st.write("")

    left, right = st.columns([3, 2])
    with left:
        st.subheader("What contributes to the score")
        st.plotly_chart(charts.component_bars(data["view"]), use_container_width=True, config=charts.CHART_CONFIG)
        weights = ", ".join(f"{c['label']} {c['weight']}%" for c in data["cfg"]["components"] if c["primary"])
        st.caption(f"Weights: {weights}.")
        if state.show_optional():
            st.caption("Localization Readiness is optional and carries no weight in the market-potential score.")
    with right:
        st.subheader("Top markets")
        top = data["regions"]["top"][:3]
        if not top:
            html(theme.note("No region has enough evidence to be ranked.", "bad"))
        for r in top:
            html(f'<div class="kz-card" style="margin-bottom:8px; padding:10px 14px;">'
                 f'<div class="kz-row"><span><b style="color:{theme.INK}">#{r["rank"]} {esc(r["state"])}</b></span>'
                 f'<span><b>{r["score"]}</b>/100</span></div>'
                 f'<div class="kz-sub">Confidence {r["confidence"]}% &middot; {esc(r["recommended_language"])}'
                 f' &middot; {esc(r["preferred_platform"])}</div></div>')
        if data["regions"]["suppressed"]:
            st.caption(f"{len(data['regions']['suppressed'])} regions are not ranked (insufficient evidence).")

    st.subheader("Source coverage")
    _coverage(data)
    with st.expander("Title metadata, Content DNA and audience fit", expanded=False):
        _dna(data)
