"""New Analysis: title intake form, then a staged progress screen."""
import time

import streamlit as st

from kizuna import intake, state, theme
from kizuna.theme import esc, html

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]
OUTCOMES = {"Normal": "normal", "Partial data (YouTube unavailable)": "partial", "Failure (AniList timeout)": "failure"}
KEYS = ["na_title", "na_synopsis", "na_format", "na_primary_genre", "na_source_material", "na_release_period",
        "na_target_platform", "na_english_title", "na_secondary_genres", "na_age_rating", "na_studio",
        "na_director", "na_cast", "na_episodes", "na_themes", "na_franchise_status", "na_intended_audience",
        "na_target_languages", "na_target_states", "na_budget_band", "na_release_month", "na_trailer_url",
        "na_outcome"]
STAGE_ICON = {"done": "&#10003;", "running": "&#9679;", "pending": "&#9675;", "failed": "&#10007;"}


def _csv(text):
    return [t.strip() for t in (text or "").split(",") if t.strip()]


def _payload(cfg, poster):
    g = st.session_state.get
    return {
        "title": g("na_title") or "", "synopsis": g("na_synopsis") or "", "format": g("na_format"),
        "primary_genre": g("na_primary_genre"), "source_material": g("na_source_material"),
        "release_period": (g("na_release_period") or "").strip(), "target_platform": g("na_target_platform"),
        "english_title": g("na_english_title") or "", "secondary_genres": g("na_secondary_genres") or [],
        "age_rating": g("na_age_rating"), "studio": g("na_studio") or "", "director": g("na_director") or "",
        "cast": _csv(g("na_cast")), "episodes": (g("na_episodes") or "").strip(),
        "themes": _csv(g("na_themes")), "franchise_status": g("na_franchise_status"),
        "intended_audience": g("na_intended_audience") or "", "target_languages": g("na_target_languages") or [],
        "target_states": g("na_target_states") or [], "budget_band": g("na_budget_band"),
        "release_month": g("na_release_month"), "trailer_url": g("na_trailer_url") or "",
        "poster_name": poster.name if poster is not None else "",
    }


def _form(cfg):
    st.subheader("Basic information")
    st.text_input("Title *", key="na_title", placeholder="Shadow Bloom", max_chars=200)
    st.text_area("Synopsis *", key="na_synopsis", height=120, max_chars=intake.MAX_TEXT,
                 placeholder="A teenage spirit guardian must protect...")
    c1, c2, c3 = st.columns(3)
    c1.selectbox("Content format *", cfg["content_formats"], index=None, key="na_format", placeholder="Select")
    c2.selectbox("Primary genre *", intake.GENRES, index=None, key="na_primary_genre", placeholder="Select")
    c3.selectbox("Source material *", intake.SOURCE_MATERIAL, index=None, key="na_source_material",
                 placeholder="Select")
    c1, c2, c3 = st.columns(3)
    c1.text_input("Expected release period *", key="na_release_period", placeholder="March 2027")
    c2.selectbox("Target platform *", intake.PLATFORMS, index=None, key="na_target_platform", placeholder="Select")
    c3.selectbox("Age rating", intake.AGE_RATINGS, index=None, key="na_age_rating", placeholder="Optional")

    st.subheader("Content details")
    c1, c2 = st.columns(2)
    c1.text_input("English title", key="na_english_title")
    c2.multiselect("Secondary genres", intake.GENRES, key="na_secondary_genres")
    c1, c2, c3 = st.columns(3)
    c1.text_input("Studio", key="na_studio")
    c2.text_input("Director", key="na_director")
    c3.text_input("Episodes or duration", key="na_episodes", placeholder="12 episodes")
    c1, c2 = st.columns(2)
    c1.text_input("Primary themes (comma separated)", key="na_themes")
    c2.text_input("Cast (comma separated)", key="na_cast")
    c1, c2 = st.columns(2)
    c1.selectbox("Franchise status", intake.FRANCHISE_STATUS, index=None, key="na_franchise_status",
                 placeholder="Optional")
    c2.text_input("Intended audience", key="na_intended_audience", placeholder="Youth and anime fans")

    st.subheader("India market assumptions")
    c1, c2 = st.columns(2)
    c1.multiselect("Target languages", cfg["languages"], key="na_target_languages")
    c2.multiselect("Target states", sorted(cfg["states"]), key="na_target_states")
    c1, c2 = st.columns(2)
    c1.selectbox("Marketing budget", intake.BUDGET_BANDS, index=None, key="na_budget_band", placeholder="Optional")
    c2.selectbox("Proposed release month", MONTHS, index=None, key="na_release_month", placeholder="Optional")

    st.subheader("Assets and partner data")
    c1, c2 = st.columns(2)
    poster = c1.file_uploader("Poster (PNG, JPG or WebP, up to 5 MB)", type=list(intake.POSTER_TYPES),
                              key="na_poster")
    c2.text_input("Trailer or teaser URL", key="na_trailer_url", placeholder="https://www.youtube.com/watch?v=...")
    c2.file_uploader("Partner historical data (CSV) - coming later", type=["csv"], disabled=True, key="na_partner")
    return poster


def _summary(cfg, payload, errors, poster_error):
    pct, missing = intake.completeness(payload)
    with st.container(border=True):
        st.markdown("**Input completeness**")
        html(f'<div class="kz-big">{pct}<small> %</small></div>' + theme.meter(pct))
        req_missing = [label for key, label in intake.REQUIRED if not intake._filled(payload.get(key))]
        if req_missing:
            html(theme.note("Required: " + ", ".join(req_missing), "bad"))
        else:
            html(theme.note("All required fields are filled.", "info"))
        opt_missing = [label for key, label in intake.OPTIONAL if not intake._filled(payload.get(key))]
        if opt_missing:
            st.caption("Optional fields still empty reduce confidence: " + ", ".join(opt_missing[:6])
                       + ("..." if len(opt_missing) > 6 else ""))
        st.markdown("**Automatic enrichment after submit**")
        st.caption("AniList metadata, related titles, Google Trends, YouTube statistics, Wikimedia activity, "
                   "regional language context and historical comparables. You do not enter these.")
        st.divider()
        st.radio("Simulate backend outcome (prototype only)", list(OUTCOMES), key="na_outcome")
        problems = errors + ([poster_error] if poster_error else [])
        run = st.button("Run Market Analysis", type="primary", use_container_width=True, disabled=bool(problems))
        for p in problems:
            if not p.endswith("is required."):
                st.error(p)
    return run


def _stage_html(stages):
    return "".join(f'<div class="kz-stage">{STAGE_ICON[s["state"]]} &nbsp; {esc(s["name"])}</div>' for s in stages)


def _sources_html(sources):
    kinds = {"Available": "good", "Cached data used": "info", "Unavailable": "warn", "Failed (timeout)": "bad"}
    return "".join(
        f'<div class="kz-row"><span>{esc(s["name"])}</span><span>{theme.badge(s["status"], kinds.get(s["status"], "neutral"))}</span></div>'
        for s in sources)


def _running(api):
    job_id = st.session_state["na_job"]
    title = st.session_state.get("na_title", "title")
    st.title(f"Analysing {title}")
    box = st.empty()
    while True:
        job = api.get_job(job_id)
        with box.container():
            st.progress(job["progress"] / 100, text=f"Estimated progress: {job['progress']}%")
            c1, c2 = st.columns(2)
            c1.markdown("**Pipeline**")
            c1.markdown(_stage_html(job["stages"]), unsafe_allow_html=True)
            c2.markdown("**Source status**")
            c2.markdown(_sources_html(job["sources"]), unsafe_allow_html=True)
        if job["status"] != "running":
            break
        time.sleep(0.25)

    if job["status"] == "failed":
        st.error("The analysis could not be completed.")
        st.write(f"{job['error']} Your inputs have been saved. Retry the failed collection or continue using cached data.")
        c1, c2, c3 = st.columns(3)
        if c1.button("Retry", type="primary", use_container_width=True):
            api.retry_job(job_id)
            st.rerun()
        if c2.button("Use Cached Data", use_container_width=True):
            api.use_cached_data(job_id)
            st.rerun()
        if c3.button("Edit inputs", use_container_width=True):
            st.session_state["na_stage"] = "form"
            st.rerun()
        return

    if job["status"] == "partial":
        st.warning("Analysis completed with limited evidence. Some sources were unavailable or served from cache, "
                   "and confidence has been adjusted accordingly.")
        time.sleep(1.5)
    else:
        st.success("Analysis complete.")
        time.sleep(0.6)
    state.set_active_title(job["title_id"])
    st.session_state["na_stage"] = "form"
    state.goto("results")


def render():
    api, cfg = state.get_api(), state.get_cfg()
    for k in KEYS:  # keep widget values alive while the form is not rendered
        if k in st.session_state:
            st.session_state[k] = st.session_state[k]

    if st.session_state.get("na_stage") == "running":
        _running(api)
        return

    st.title("Analyse a New Japanese Title")
    st.caption("Fields marked * are required. Everything else is optional and improves confidence.")
    left, right = st.columns([3, 1.4])
    with left:
        poster = _form(cfg)
    payload = _payload(cfg, poster)
    errors = intake.validate(payload)
    poster_error = None
    if poster is not None and poster.size > intake.MAX_POSTER_BYTES:
        poster_error = "Poster is larger than 5 MB."
    with right:
        run = _summary(cfg, payload, errors, poster_error)
    if run:
        outcome = OUTCOMES[st.session_state.get("na_outcome", "Normal")]
        st.session_state["na_job"] = api.start_analysis(payload, outcome=outcome)
        st.session_state["na_stage"] = "running"
        st.rerun()
