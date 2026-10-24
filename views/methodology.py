"""Methodology: sources, versions, scoring weights, limitations and the session audit log."""
import pandas as pd
import streamlit as st

from kizuna import state

SOURCE_GUARDRAILS = {
    "anilist": ("Synopsis, genres, tags, studios, popularity", "Popularity is used as a historical outcome only; post-release leakage is blocked."),
    "google_trends": ("Relative search demand, momentum, seasonality, state interest", "Cache exports; values are relative 0-100; lower confidence for sparse terms."),
    "youtube": ("Trailer views, likes, comments, engagement velocity", "Respect quotas; global metrics are not India-specific."),
    "wikimedia": ("Page-view growth and sustained interest", "Treated as curiosity, not consumption."),
    "census": ("Language and population context", "Table year is labelled; not current behaviour."),
    "datameet": ("State boundaries for the map", "Versioned boundary file; state-name mapping validated."),
    "partner_csv": ("Licensing, spend, completion, revenue", "Contracted schema, restricted access; coming later."),
}


def render():
    tid = state.active_title()
    api, cfg = state.get_api(), state.get_cfg()
    st.title("Data and Methodology")
    st.caption("How the numbers are produced and what they can and cannot tell you.")

    if tid:
        analysis, sources = api.get_analysis(tid), api.get_sources(tid)
        st.subheader("Versions")
        st.table(pd.DataFrame([
            ("Analysis", analysis["analysis_id"]), ("Result version", analysis["result_version"]),
            ("Model", f"{analysis['model_version']} ({analysis['model_used']})"),
            ("Scoring configuration", analysis["scoring_config_version"]),
            ("Feature snapshot", analysis["feature_snapshot_id"]), ("Created", analysis["created_at"]),
        ], columns=["Item", "Value"]).set_index("Item"))

        st.subheader("Sources")
        st.dataframe(pd.DataFrame([{
            "Source": s["name"], "Contribution": SOURCE_GUARDRAILS.get(s["id"], ("", ""))[0],
            "Guardrail": SOURCE_GUARDRAILS.get(s["id"], ("", ""))[1],
            "Status": s["status"].replace("_", " "), "Mode": s["mode"],
        } for s in sources]), hide_index=True, use_container_width=True)

    st.subheader("Active scoring weights")
    st.dataframe(pd.DataFrame([{"Component": c["label"], "Weight %": c["weight"],
                                "Type": "Primary" if c["primary"] else "Optional (no weight)"}
                               for c in cfg["components"]]), hide_index=True, use_container_width=True)
    st.markdown("Market Potential = 25% Content Fit + 25% Demand Momentum + 20% Regional Opportunity + "
                "15% Engagement Quality + 15% Comparable Performance. Weights are configuration, not code.")
    st.dataframe(pd.DataFrame([{"Confidence factor": f["label"], "Weight": f["weight"]}
                               for f in cfg["confidence_factors"]]), hide_index=True, use_container_width=True)
    st.caption("Potential and confidence are separate outputs. A regional score is not ranked when its evidence "
               f"strength is below {cfg['regional']['suppress_below_evidence']}.")

    st.subheader("Limitations")
    for line in [
        "Prototype: all values come from mock JSON. Titles marked as created in this session reuse a mock template.",
        "Scores estimate market potential from public demand proxies; they are not revenue forecasts.",
        "Comparable titles are real historical titles with illustrative, made-up performance scores.",
        "Scenario effects are fixed illustrative parameters, not retrained model output.",
        "Map boundaries come from a public GeoJSON, not a versioned DataMeet release.",
        "PDF exports replace non-Latin characters (for example Japanese) with '?'.",
    ]:
        st.markdown(f"- {line}")

    st.subheader("Audit log (this session)")
    log = state.audit_log()
    if log:
        st.dataframe(pd.DataFrame(log), hide_index=True, use_container_width=True)
    else:
        st.caption("No overrides or approvals recorded yet.")
