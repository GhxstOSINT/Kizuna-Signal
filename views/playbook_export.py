"""Launch Playbook & Export: recommendation, human approval gate and report downloads."""
import streamlit as st

from kizuna import engine, report, state, theme
from kizuna.theme import esc, html


def _playbook(reco):
    c1, c2 = st.columns(2)
    with c1:
        html(theme.row("Platform", reco["platform"]) + theme.row("Launch window", reco["launch_window"]))
        st.markdown("**Priority markets**")
        html(" ".join(theme.badge(m, "info") for m in reco["priority_markets"]))
        st.markdown("**Localization**")
        for x in reco["localization"]:
            st.markdown(f"- {x}")
        st.markdown("**Target audience**")
        for x in reco["target_audience"]:
            st.markdown(f"- {x}")
    with c2:
        st.markdown("**Marketing positioning**")
        st.write(reco["positioning"])
        st.markdown("**Campaign strategy**")
        for x in reco["campaign"]:
            st.markdown(f"- {x}")
    st.markdown("**Risks and mitigations**")
    for r in reco["risks"]:
        st.markdown(f"- **{r['risk']}**: {r['mitigation']}")


def _items(reco):
    for item in reco["items"]:
        with st.container(border=True):
            st.markdown(f"**{item['topic']}**: {item['decision']}")
            html(theme.row("Expected benefit", item["expected_benefit"])
                 + theme.row("Confidence", f"{item['confidence']}%")
                 + theme.row("Principal risk", item["principal_risk"]))
            st.caption("Evidence: " + "; ".join(item["evidence"]))


def _approval(tid, view):
    approval = state.get_approval(tid)
    st.subheader("Human approval")
    st.caption("A recommendation is only marked as a launch decision after an analyst accepts it. "
               "Changing sources or comparables afterwards clears the approval.")
    if approval and approval["status"] == "accepted":
        st.success(f"Accepted by {approval['by']} on {approval['time']}."
                   + (f" Note: {approval['reason']}" if approval["reason"] else ""))
        if st.button("Withdraw approval", key=f"withdraw_{tid}"):
            state.reset_approval(tid, "Approval withdrawn by analyst.")
            st.rerun()
        return True
    if approval and approval["status"] == "rejected":
        st.error(f"Rejected by {approval['by']} on {approval['time']}. Reason: {approval['reason']}")
    elif view["low_confidence"]:
        html(theme.note("Confidence is low. Accepting only records the recommendation to gather more evidence.", "bad"))
    name = st.text_input("Approver name", value=state.analyst_name(), key=f"appr_name_{tid}")
    reason = st.text_area("Note or reason", key=f"appr_reason_{tid}", height=80)
    c1, c2 = st.columns(2)
    if c1.button("Accept recommendation", type="primary", use_container_width=True, key=f"accept_{tid}",
                 disabled=not name.strip()):
        state.set_approval(tid, "accepted", name.strip(), reason.strip())
        st.rerun()
    if c2.button("Reject", use_container_width=True, key=f"reject_{tid}",
                 disabled=not (name.strip() and reason.strip()), help="A reason is required to reject."):
        state.set_approval(tid, "rejected", name.strip(), reason.strip())
        st.rerun()
    return False


def _exports(data, tid, accepted):
    st.subheader("Reports and exports")
    if not accepted:
        st.info("Exports unlock after the recommendation is accepted.")
    results = engine.scenario_results(data["view"], data["scenarios"], data["cfg"])
    recommended = engine.recommend_scenario(results[1:], data["cfg"])
    ctx = report.make_context(data, results, recommended, state.get_approval(tid), state.audit_log())
    slug = tid.replace("_", "-")
    items = [
        ("Executive brief (PDF, 1 page)", lambda: report.executive_brief_pdf(ctx), f"{slug}-executive-brief.pdf", "application/pdf"),
        ("Full analysis (PDF)", lambda: report.full_report_pdf(ctx), f"{slug}-full-analysis.pdf", "application/pdf"),
        ("Regional scores (CSV)", lambda: report.regional_csv(ctx), f"{slug}-regional-scores.csv", "text/csv"),
        ("India map (interactive HTML)", lambda: report.map_html(ctx), f"{slug}-india-map.html", "text/html"),
        ("Scenario comparison (CSV)", lambda: report.scenario_csv(ctx), f"{slug}-scenarios.csv", "text/csv"),
    ]
    cols = st.columns(len(items))
    for col, (label, fn, fname, mime) in zip(cols, items):
        col.download_button(label, data=fn, file_name=fname, mime=mime, disabled=not accepted,
                            use_container_width=True, key=f"dl_{tid}_{fname}")
    st.text_input("Read-only share link (mock, not functional in the prototype)",
                  value=f"https://kizuna.example/share/{data['analysis']['analysis_id']}", disabled=True)


def render():
    tid = state.active_title()
    if tid is None:
        st.info("No title has been analysed yet. Start from the Portfolio page.")
        return
    data = state.load(tid)
    view, reco = data["view"], data["reco"]
    st.title(f"Launch Playbook: {data['title']['title']}")
    html(theme.decision_badge(view["label"]) + " " + theme.badge(f"Confidence {view['confidence']}%",
                                                                  theme.confidence_kind(view["confidence"]))
         + " " + theme.badge(f"Score {view['overall']}/100"))
    st.markdown(f"#### {reco['headline']}")
    if state.has_overrides(tid):
        html(theme.note("Based on your current source and comparable overrides.", "info"))

    _playbook(reco)
    st.divider()
    st.subheader("Recommendations with evidence")
    _items(reco)
    st.divider()
    accepted = _approval(tid, view)
    st.divider()
    _exports(data, tid, accepted)
