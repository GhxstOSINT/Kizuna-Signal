"""Portfolio: the landing page with one card per analysed title."""
import streamlit as st

from kizuna import state, theme
from kizuna.theme import esc, html


def _primary_language(aff):
    return max(aff, key=lambda a: a["affinity"])["language"]


def _card(p, data, reco, aff):
    view, meta, regions = data["view"], data["title"], data["regions"]
    top_state = regions["top"][0]["state"] if regions["top"] else "Insufficient evidence"
    status_kind = {"complete": "good", "partial": "warn"}.get(p["status"], "neutral")
    conf_kind = theme.confidence_kind(view["confidence"])
    lo, hi = view["interval"]
    html(f"""
<div class="kz-card tall">
  {theme.poster(meta['title'], meta.get('accent', theme.PRIMARY))}
  <div class="kz-title">{esc(meta['title'])}</div>
  <div class="kz-sub">{esc(meta['format'])} &middot; {esc(', '.join(meta['genres'][:2]))}</div>
  <div style="margin:8px 0 10px 0;">{theme.badge(p['status'].capitalize(), status_kind)}
    {theme.decision_badge(view['label'])}</div>
  <div class="kz-label">Market potential</div>
  <div class="kz-big">{view['overall']}<small> / 100</small></div>
  {theme.meter(view['overall'])}
  <div class="kz-row"><span>Confidence</span><span>{theme.badge(f"{view['confidence_band']} - {view['confidence']}%", conf_kind)}</span></div>
  {theme.row('Expected range', f'{lo}-{hi}')}
  {theme.row('Top market', top_state)}
  {theme.row('Primary language', _primary_language(aff))}
  {theme.row('Recommended platform', reco['platform'])}
  {theme.row('Last analysis', p['last_analysis'])}
</div>""")


def render():
    api = state.get_api()
    head, action = st.columns([4, 1], vertical_alignment="center")
    head.title("Portfolio")
    head.caption("Pre-release intelligence for Japanese media entering India.")
    if action.button("Analyse New Title", type="primary", icon=":material/add:", use_container_width=True):
        state.goto("new_analysis")

    projects = api.list_projects()
    if not projects:
        st.info("No title has been analysed yet. Add a Japanese title to discover its potential "
                "across Indian regional markets.")
        if st.button("Analyse New Title", key="empty_cta", type="primary"):
            state.goto("new_analysis")
        return

    s1, s2 = st.columns([3, 1])
    query = s1.text_input("Search titles", placeholder="Search by title", label_visibility="collapsed")
    formats = ["All formats"] + sorted({p["format"] for p in projects})
    fmt = s2.selectbox("Format", formats, label_visibility="collapsed")

    shown = [p for p in projects
             if query.strip().lower() in p["title"].lower() and fmt in ("All formats", p["format"])]
    if not shown:
        st.info("No titles match your search or filter.")
        return

    snapshots = []
    for project in shown:
        title_id = project["title_id"]
        data = state.load(title_id)
        snapshots.append({
            "project": project,
            "data": data,
            "recommendation": api.get_recommendation(title_id),
            "language_affinity": api.get_regions(title_id)["language_affinity"],
        })

    scores = [snapshot["data"]["view"]["overall"] for snapshot in snapshots]
    confidences = [snapshot["data"]["view"]["confidence"] for snapshot in snapshots]
    priority_states = {
        row["state"]
        for snapshot in snapshots
        for row in snapshot["data"]["regions"]["top"]
    }
    avg_score = round(sum(scores) / len(scores))
    avg_confidence = round(sum(confidences) / len(confidences))
    mode = "LIVE API" if hasattr(api, "base_url") else "OFFLINE DEMO"
    theme.html(f"""
<div class="kz-ticker"><span class="dot"></span><span>{mode}</span><span class="sep">/</span>
<span>{len(shown)} titles in view</span><span class="sep">/</span>
<span>Explainable scoring</span><span class="sep">/</span><span>India regional intelligence</span></div>
<section class="kz-portfolio-hero">
  <div class="kz-eyebrow">Kizuna Signal &nbsp;/&nbsp; Market intelligence</div>
  <h2>See the next signal before launch.</h2>
  <p>Compare market potential, evidence confidence and regional opportunity—then turn the strongest signals into a launch plan.</p>
</section>
<div class="kz-hero-stats">
  <div class="kz-hero-stat"><strong>{len(shown)}</strong><span>Titles in view</span></div>
  <div class="kz-hero-stat"><strong>{avg_score}<small style="font:400 .82rem Arial,sans-serif;color:#70747a;"> / 100</small></strong><span>Average potential</span></div>
  <div class="kz-hero-stat"><strong>{avg_confidence}%</strong><span>Average confidence</span></div>
  <div class="kz-hero-stat"><strong>{len(priority_states)}</strong><span>Priority states</span></div>
</div>""")
    st.subheader("Analysis portfolio")

    cols = st.columns(3)
    for i, snapshot in enumerate(snapshots):
        p = snapshot["project"]
        tid = p["title_id"]
        with cols[i % 3]:
            _card(p, snapshot["data"], snapshot["recommendation"], snapshot["language_affinity"])
            if st.button("Open results", key=f"open_{tid}", use_container_width=True):
                state.set_active_title(tid)
                state.goto("results")
        if i % 3 == 2:
            cols = st.columns(3)
