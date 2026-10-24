"""Scenario Lab: controlled overrides on the frozen analysis, compared against the base strategy."""
import streamlit as st

from kizuna import charts, engine, state, theme
from kizuna.theme import html


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
        for col, (lever, spec) in zip(cols, cfg["levers"].items(), strict=False):
            options = list(spec["options"])
            base_opt = sc["base"]["levers"][lever]
            custom[lever] = col.selectbox(spec["label"], options, index=options.index(base_opt),
                                          format_func=lambda o, s=spec: s["options"][o]["label"],
                                          key=f"lever_{tid}_{lever}")

        api = state.get_api()
        if hasattr(api, "create_scenario"):
            if st.button("Evaluate with live backend", type="primary", key=f"eval_scenario_{tid}"):
                localization = {
                    "subs_hindi": "subtitles",
                    "dub_hindi_subs_regional": "dub",
                    "multilingual_dub": "multilingual_dub",
                    "english_subs_only": "subtitles",
                }[custom["localization"]]
                platform = {
                    "ott": "OTT", "theatrical": "Theatrical", "tv": "Television",
                    "digital_first": "Digital-first", "hybrid": "Hybrid (OTT + theatrical)",
                }[custom["distribution"]]
                regions = data["regions"]["ranked"]
                states = [row.get("state") for row in regions[:5] if row.get("state")]
                languages = list(dict.fromkeys(
                    row.get("recommended_language") for row in regions[:5]
                    if row.get("recommended_language")
                ))
                payload = {
                    "name": f"Streamlit scenario: {custom['localization']} / {custom['distribution']}",
                    "target_platform": platform,
                    "localization_mode": localization,
                    "marketing_budget": custom["marketing_budget"],
                    "target_states": states if custom["geography"] != "national" else None,
                    "target_languages": languages if custom["geography"] != "national" else None,
                    "disabled_sources": state.get_overrides(tid)["disabled_sources"],
                }
                try:
                    st.session_state[f"backend_scenario_{tid}"] = api.create_scenario(tid, payload)
                    st.success("Scenario evaluated and saved by the backend.")
                except (RuntimeError, KeyError) as exc:
                    st.error(f"Could not evaluate scenario: {exc}")

            backend_scenario = st.session_state.get(f"backend_scenario_{tid}")
            if backend_scenario:
                result = backend_scenario["result"]
                st.subheader("Backend-evaluated scenario")
                metric_cols = st.columns(4)
                metric_cols[0].metric("Market potential", f"{result['scenario_score']:.0f}",
                                      f"{result['score_delta']:+.1f}")
                metric_cols[1].metric("Confidence", f"{result['scenario_confidence']:.0f}%",
                                      f"{result['confidence_delta']:+.1f}%")
                metric_cols[2].metric("Estimated cost", result["cost_level"].title())
                metric_cols[3].metric("Regional reach", result["reach_level"].title())
                st.caption("Release-window choice is not included in the current backend scenario contract.")
                st.write("**Backend recommendation:**", result["recommendation"]["decision"])

    results = engine.scenario_results(view, sc, cfg)
    if custom != sc["base"]["levers"] and custom not in [p["levers"] for p in sc["presets"]]:
        results.append(("Custom scenario", engine.scenario_result(view, sc, custom, cfg)))

    cols = st.columns(len(results))
    for col, (name, r) in zip(cols, results, strict=False):
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
