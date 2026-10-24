"""Results: decision, regional intelligence, comparables, drivers, confidence and sources."""
import streamlit as st

from kizuna import state
from sections import comparables, confidence, decision, drivers, regions


def render():
    tid = state.active_title()
    if tid is None:
        st.info("No title has been analysed yet. Start from the Portfolio page.")
        return
    data = state.load(tid)
    st.title(f"Results: {data['title']['title']}")
    tabs = st.tabs(["Decision", "Regional Intelligence", "Comparables", "Drivers", "Confidence & Sources"])
    with tabs[0]:
        decision.render(data, tid)
    with tabs[1]:
        regions.render(data, tid)
    with tabs[2]:
        comparables.render(data, tid)
    with tabs[3]:
        drivers.render(data, tid)
    with tabs[4]:
        confidence.render(data, tid)
