"""Kizuna Signal: Streamlit prototype entry point."""
import streamlit as st

from kizuna import state, theme
from kizuna.config import APP_NAME
from views import methodology, new_analysis, playbook_export, portfolio, results, scenario_lab

st.set_page_config(page_title=APP_NAME, page_icon=":material/radar:", layout="wide")
theme.inject_css()

PAGES = {
    "portfolio": st.Page(portfolio.render, title="Portfolio", icon=":material/dashboard:",
                         url_path="portfolio", default=True),
    "new_analysis": st.Page(new_analysis.render, title="New Analysis", icon=":material/add_circle:",
                            url_path="new-analysis"),
    "results": st.Page(results.render, title="Results", icon=":material/insights:", url_path="results"),
    "scenario_lab": st.Page(scenario_lab.render, title="Scenario Lab", icon=":material/science:",
                            url_path="scenario-lab"),
    "playbook": st.Page(playbook_export.render, title="Playbook & Export", icon=":material/rocket_launch:",
                        url_path="playbook"),
    "methodology": st.Page(methodology.render, title="Methodology", icon=":material/menu_book:",
                           url_path="methodology"),
}
state.register_pages(PAGES)

with st.sidebar:
    st.markdown(f"### {APP_NAME}")
    st.caption("Pre-release intelligence for Japanese media in India")
    projects = state.get_api().list_projects()
    ids = [p["title_id"] for p in projects]
    names = {p["title_id"]: p["title"] for p in projects}
    active = state.active_title()
    if st.session_state.get("sidebar_title") != active:
        st.session_state["sidebar_title"] = active
    st.selectbox("Active title", ids, format_func=lambda i: names.get(i, i), key="sidebar_title",
                 on_change=lambda: state.set_active_title(st.session_state["sidebar_title"]))
    st.toggle("Show optional components", key="show_optional",
              help="Adds Localization Readiness. It carries no weight in the market-potential score.")
    st.text_input("Analyst name", key="analyst_name", value="Analyst",
                  help="Recorded in the audit log for overrides and approvals.")

st.navigation(list(PAGES.values())).run()
