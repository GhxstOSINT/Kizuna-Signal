"""Results tab: positive and negative prediction drivers with per-driver evidence."""
import streamlit as st

from kizuna import charts, theme
from kizuna.theme import esc, html


def _row(d, sources_by_id, comp_labels):
    c = st.columns([1, 6, 3, 1.4], vertical_alignment="center")
    color = theme.GOOD if d["points"] > 0 else theme.BAD
    if not d["active"]:
        color = theme.MUTED
    c[0].markdown(f"<b style='color:{color}'>{d['points']:+.1f}</b>", unsafe_allow_html=True)
    label = esc(d["label"]) + ("  " + theme.badge("source disabled", "neutral") if not d["active"] else "")
    c[1].markdown(label, unsafe_allow_html=True)
    c[2].markdown(f"<span class='kz-sub'>{esc(comp_labels.get(d['component'], d['component']))}</span>",
                  unsafe_allow_html=True)
    with c[3].popover("Why?", use_container_width=True):
        st.markdown(f"**{d['label']}**")
        st.write(d["why"])
        st.caption("Evidence sources")
        for sid in d["source_ids"]:
            s = sources_by_id.get(sid)
            if s:
                html(theme.row(s["name"], s["status"].replace("_", " ").capitalize()
                               + (f" ({s['mode']})" if s["mode"] not in ("none", "live") else "")))
        if not d["active"]:
            st.caption("All sources behind this driver are disabled, so it is excluded from the explanation.")


def render(data, tid):
    drivers = data["view"]["drivers"]
    sources_by_id = {s["id"]: s for s in data["sources"]}
    comp_labels = {c["id"]: c["label"] for c in data["cfg"]["components"]}
    st.subheader("Prediction drivers")
    st.caption("Contribution of each factor to the market-potential score, in points (SHAP-style attribution). "
               "Greyed drivers depend only on sources you have disabled.")
    st.plotly_chart(charts.driver_bars(drivers), use_container_width=True, config=charts.CHART_CONFIG)

    pos = sorted((d for d in drivers if d["points"] > 0), key=lambda d: -d["points"])
    neg = sorted((d for d in drivers if d["points"] < 0), key=lambda d: d["points"])
    left, right = st.columns(2)
    with left:
        st.markdown("#### Positive drivers")
        for d in pos:
            _row(d, sources_by_id, comp_labels)
    with right:
        st.markdown("#### Negative drivers")
        for d in neg:
            _row(d, sources_by_id, comp_labels)
    st.caption(f"Explanation based on analysis {data['analysis']['analysis_id']}, model "
               f"{data['analysis']['model_version']}, scoring config {data['analysis']['scoring_config_version']}.")
