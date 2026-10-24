"""Results tab: India opportunity map, ranking, language affinity and state detail."""
import pandas as pd
import streamlit as st

from kizuna import charts, theme
from kizuna.theme import esc, html


def _on_map_select(tid):
    event = st.session_state.get(f"map_{tid}")
    points = (event or {}).get("selection", {}).get("points", []) if event else []
    if points:
        loc = points[0].get("location")
        if loc:
            st.session_state[f"sel_{tid}"] = loc


def _detail(region):
    if region["suppressed"]:
        html(theme.note(f"{region['state']}: insufficient evidence (strength {region['evidence_strength']}). "
                        "This region is not ranked and its score is shown for reference only.", "bad"))
        st.caption(f"Reference score {region['score']}, confidence {region['confidence']}%.")
        return
    flag = {"limited": theme.badge("Limited evidence", "warn"), "ok": theme.badge("Evidence OK", "good")}[region["evidence_flag"]]
    html(f'<div class="kz-title">{esc(region["state"])}</div>'
         f'<div class="kz-sub">Rank #{region["rank"]} &nbsp; {flag}</div>')
    c1, c2 = st.columns(2)
    c1.metric("Opportunity score", f"{region['score']}/100")
    c2.metric("Confidence", f"{region['confidence']}%")
    html("".join([
        theme.row("Demand momentum", region["demand_momentum"]),
        theme.row("Recommended language", region["recommended_language"]),
        theme.row("Secondary language", region["secondary_language"]),
        theme.row("Preferred platform", region["preferred_platform"]),
        theme.row("Audience segment", region["audience_segment"]),
        theme.row("Evidence strength", region["evidence_strength"]),
    ]))
    st.markdown("**Why this state ranks here**")
    for reason in region["reasons"]:
        st.markdown(f"- {reason}")


def render(data, tid):
    ranking = data["regions"]
    st.subheader("Regional opportunity")
    st.caption("India is treated as many language and cultural markets. Grey regions have too little evidence "
               "to rank.")
    if ranking["top"]:
        cols = st.columns(3)
        for col, r in zip(cols, ranking["top"][:3]):
            with col:
                html(f'<div class="kz-card" style="padding:12px 16px;">'
                     f'<div class="kz-label">#{r["rank"]} {esc(r["state"])}</div>'
                     f'<div class="kz-big" style="font-size:2rem;">{r["score"]}<small> / 100</small></div>'
                     f'<div class="kz-sub" style="margin-top:4px;">Confidence {r["confidence"]}% &middot; '
                     f'{esc(r["recommended_language"])}</div></div>')
    else:
        html(theme.note("No region has enough evidence to be ranked.", "bad"))

    st.write("")
    all_states = ranking["ranked"] + ranking["suppressed"]
    options = [r["state"] for r in all_states]
    key = f"sel_{tid}"
    if st.session_state.get(key) not in options:
        st.session_state[key] = options[0]
    by_state = {r["state"]: r for r in all_states}

    left, right = st.columns([3, 2])
    with left:
        fig = charts.choropleth(ranking, st.session_state[key])
        st.plotly_chart(fig, use_container_width=True, config=charts.CHART_CONFIG, key=f"map_{tid}",
                        on_select=lambda: _on_map_select(tid), selection_mode="points")
    with right:
        def label(s):
            r = by_state[s]
            return f"#{r['rank']} {s}" if not r["suppressed"] else f"{s} (not ranked)"
        st.selectbox("Region", options, format_func=label, key=key)
        _detail(by_state[st.session_state[key]])

    st.divider()
    t1, t2 = st.columns([3, 2])
    with t1:
        st.subheader("State ranking")
        df = pd.DataFrame([{
            "Rank": r["rank"], "State": r["state"], "Score": r["score"], "Confidence %": r["confidence"],
            "Momentum": r["demand_momentum"], "Language": r["recommended_language"],
            "Platform": r["preferred_platform"],
            "Evidence": "Limited" if r["evidence_flag"] == "limited" else "OK",
        } for r in ranking["ranked"]])
        st.dataframe(df, hide_index=True, use_container_width=True, height=360,
                     column_config={"Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d")})
        if ranking["suppressed"]:
            with st.expander(f"Not ranked: {len(ranking['suppressed'])} regions with insufficient evidence"):
                st.write(", ".join(r["state"] for r in ranking["suppressed"]))
    with t2:
        st.subheader("Language affinity")
        st.plotly_chart(charts.language_bars(data["language_affinity"]), use_container_width=True,
                        config=charts.CHART_CONFIG)
