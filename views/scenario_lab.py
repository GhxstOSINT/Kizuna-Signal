"""Scenario Lab: controlled overrides on the frozen analysis, compared against the base strategy."""
import streamlit as st

from kizuna import charts, engine, state, theme
from kizuna.theme import esc, html


def _lever_text(cfg, levers):
    return [(cfg["levers"][k]["label"], cfg["levers"][k]["options"][v]["label"]) for k, v in levers.items()]


def _metrics(col, name, r, is_base, cfg):
    with col:
        with st.container(border=True):
            st.markdown(f"**{name}**")
            st.metric("Market potential", r["score"], None if is_base or not r["delta_score"] else f"{r['delta_score']:+d}")
            st.metric("Confidence", f"{r['confidence']}%",
                      None if is_base or not r["delta_confidence"] else f"{r['delta_confidence']:+d}")
            html(theme.row("Expected range", f"{r['interval'][0]}-{r['interval'][1]}")
                 + theme.row("Estimated cost", r["cost_level"])
                 + theme.row("Regional reach", r["reach_level"])
                 + theme.row("Decision", r["label"]))
            st.caption("Settings")
            html("".join(theme.row(k, v) for k, v in _lever_text(cfg, r["levers"])))


def render():
    tid = state.active_title()
    if tid is None:
        st.info("No title has been analysed yet. Start from the Portfolio page.")
        return
    data = state.load(tid)
    cfg, sc, view = data["cfg"], data["scenarios"], data["view"]
    st.title(f"Scenario Lab: {data['title']['title']}")
    st.caption("Scenarios apply controlled overrides to the frozen analysis. They never retrain the model or "
               "change the base result.")
    if state.has_overrides(tid):
        html(theme.note("Your source and comparable overrides are included in the base figures below.", "info"))
    if view["low_confidence"]:
        html(theme.note(f"Confidence is only {view['confidence']}%. Scenario differences are indicative; gather "
                        "more evidence before acting on them.", "bad"))

    with st.expander("Build a custom scenario", expanded=True):
        cols = st.columns(len(cfg["levers"]))
        custom = {}
        for col, (lever, spec) in zip(cols, cfg["levers"].items()):
            options = list(spec["options"])
            base_opt = sc["base"]["levers"][lever]
            custom[lever] = col.selectbox(spec["label"], options, index=options.index(base_opt),
                                          format_func=lambda o, s=spec: s["options"][o]["label"],
                                          key=f"lever_{tid}_{lever}")

    results = engine.scenario_results(view, sc, cfg)
    if custom != sc["base"]["levers"] and custom not in [p["levers"] for p in sc["presets"]]:
        results.append(("Custom scenario", engine.scenario_result(view, sc, custom, cfg)))

    cols = st.columns(len(results))
    for col, (name, r) in zip(cols, results):
        _metrics(col, name, r, name == "Base strategy", cfg)

    c1, c2 = st.columns(2)
    c1.plotly_chart(charts.scenario_bars(results, "score", "Market potential"), use_container_width=True,
                    config=charts.CHART_CONFIG)
    c2.plotly_chart(charts.scenario_bars(results, "confidence", "Confidence (%)"), use_container_width=True,
                    config=charts.CHART_CONFIG)

    best, why = engine.recommend_scenario(results[1:], cfg)
    st.subheader("Recommended option")
    if best:
        st.success(why)
    else:
        st.info(why)
