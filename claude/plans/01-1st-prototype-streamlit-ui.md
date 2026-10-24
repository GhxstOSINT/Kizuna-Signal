# Plan: 1st Prototype Streamlit UI (Kizuna Signal)

Spec: `claude/specs/01-1st-prototype-streamlit-ui.md` (branch `feature/1st-prototype-streamlit-ui`, cut from `frontend`).
Plan copy to be saved at: `claude/plans/01-1st-prototype-streamlit-ui.md` (see "First action on approval").

## Context
The team needs a demo-ready Streamlit dashboard for Kizuna Signal, the explainable pre-release forecasting tool for Japanese media entering India (`Idea/Kizuna_Signal_Complete_Product_Architecture.pdf`). The backend does not exist yet, so the UI runs on mock JSON behind a thin API-client layer (`MockApi`) that mirrors the PDF's REST routes. Goal: a deterministic four-minute demo (portfolio, results, map, comparables, drivers, source toggle, scenario compare, approved export), with the layout and stack easy to change later.

The repo is greenfield. It currently has only `requirements.txt`, `.gitignore`, `data/geo/india_states.geojson` (36 regions, key `properties.ST_NM`, includes `Delhi`), a `.venv/` with the deps installed, and the local-only `claude/` folder (renamed from `.claude/`, now gitignored as `claude/`).

## First action on approval
1. `mkdir claude/plans` and save this plan to `claude/plans/01-1st-prototype-streamlit-ui.md`. (Plan mode only allows writing the system plan file now, and the user's local folder is `claude/`, not `.claude/`.)
2. Append `pytest` to `requirements.txt` and install it into `.venv`.

## Decisions already made (from the conversation)
- Five PDF components are primary: Content Fit 25, Demand Momentum 25, Regional Opportunity 20, Engagement Quality 15, Comparable Performance 15. "Localization Readiness" is optional, weight 0, and shown only behind a sidebar toggle.
- "Delhi" only, never "Delhi NCR". City names appear only in playbook text.
- Three mock titles: high-confidence (Shadow Bloom, score 78, confidence 82), low-confidence (score 81, confidence 43, "Insufficient evidence"), partial-data (one source unavailable).
- Pages: Portfolio, New Analysis (form then progress), Results (5 tabs), Scenario Lab, Playbook & Export, Methodology.
- Prototype only: no persistence beyond `st.session_state`; no live providers; no ML.

## Architecture
```
app.py                 st.navigation, sidebar (active title, optional-components toggle)
kizuna/config.py       paths/constants
kizuna/api.py          MockApi (list_projects, get_title, start_analysis, get_job, get_analysis,
                       get_regions, get_comparables, get_sources, get_scenarios, get_recommendation)
kizuna/engine.py       PURE functions, no Streamlit: recompute view from base analysis + overrides
kizuna/state.py        session_state helpers: overrides, approvals, audit log, created projects
kizuna/theme.py        CSS + HTML helpers (html.escape all user text)
kizuna/charts.py       Plotly: component bars, choropleth, SHAP bars, scenario comparison
kizuna/report.py       fpdf2 PDFs, CSV, map HTML (Latin-1-safe sanitiser)
views/*.py             6 pages, presentation only
sections/*.py          5 Results tab bodies (decision, regions, comparables, drivers, confidence)
scripts/make_mock_data.py   deterministic generator -> data/mock/**; JSON is then hand-editable
data/mock/config.json + projects.json + <title_id>/{title,analysis,regions,comparables,
                       sources,scenarios,recommendation}.json
tests/test_engine.py, test_mock_data.py, test_report.py
README.md, .streamlit/config.toml
```
Rule: views call `kizuna.api` and `kizuna.engine` only. Weights, thresholds, lever effects and decision labels live in `config.json`.

## Engine design (kizuna/engine.py)
- **Overall score** = round(sum(weight_i x component_i)) over primary components. The generator picks component values so the reference title lands on exactly 78.
- **Confidence** = weighted mean of 5 factors (completeness .20, agreement .25, comparable quality .20, regional evidence .20, freshness .15). Reference factors (88, 82, 84, 74, 85) give 82. **Interval** half-width = 2 + 0.22 x (100 - confidence), clipped to 0-100.
- **Decision label** from config thresholds: confidence < 50 -> "Insufficient evidence"; else score >= 75 Strong, >= 65 Promising, >= 50 Test before investing, else Limited.
- **Source toggle**: each source in `sources.json` carries `effect_if_disabled {components, confidence_factors}`. Disabling applies the deltas to a copy; re-enabling restores the base exactly. Unavailable sources are not toggleable. Drivers whose only sources are disabled are shown inactive.
- **Comparable include/exclude**: comparable_performance = base + (similarity-weighted mean performance of the current set - that of the default set). comparable_quality factor shifts with set size and mean similarity. Minimum 2 included. Expected/optimistic/conservative sets are id lists in `comparables.json`; the base analysis corresponds to "expected".
- **Regional suppression**: a state with evidence_strength below the config threshold is excluded from ranking and greyed on the map, with the reason shown.
- **Scenario simulation**: custom scenario = base + sum of lever-option effects (score, confidence, cost points, reach points) from `config.json`; two presets are named lever selections. The base analysis is never mutated.
- Every override and approval appends an audit entry (user, time, previous value, new value, reason).

## Build order (each step runnable and testable)
1. **Mock data**: write `scripts/make_mock_data.py`, run it, and commit the generated JSON. Verify state names against the GeoJSON.
2. **Core**: `config.py`, `api.py`, `engine.py` with `tests/test_engine.py` and `tests/test_mock_data.py`, then run `pytest`.
3. **Shell**: `app.py`, `.streamlit/config.toml`, `theme.py`, `state.py`, and Portfolio page (3 cards, search, format filter, empty state).
4. **Results**: `charts.py` and the Results tabs, in order Decision -> Regions (map, ranking, state panel) -> Comparables -> Drivers -> Confidence & Sources (toggles).
5. **New Analysis**: required/optional form, completeness indicator, simulated progress screen with the "Simulate backend outcome" selector (Normal / Partial / Failure; Retry and Use Cached Data).
6. **Scenario Lab**.
7. **Playbook & Export**: approval gate, `report.py`, `tests/test_report.py`; then Methodology page (versions, weights, limitations, audit log).
8. **README.md**, then a full demo run-through against the Definition of done.

Commits: one per build step on `feature/1st-prototype-streamlit-ui`, ending with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. No push unless asked.

## Reuse / dependencies
No existing code to reuse. Reuse `data/geo/india_states.geojson` (the Plotly `featureidkey="properties.ST_NM"`) and `requirements.txt`. Only new dependency: `pytest` (dev).

## Known risks / assumptions
- Clicking a state on the choropleth via `st.plotly_chart(on_select=...)` may be unreliable, so a state selectbox (default: top-ranked state) is the dependable fallback.
- fpdf2 core fonts are Latin-1 only. Japanese or other non-Latin input is replaced with `?` in PDFs (acceptable for the prototype).
- The GeoJSON is a public gist, not a versioned DataMeet file, so it is for the prototype only.
- The `frontend` branch is the base because `main` has no commits yet.

## Verification
- `.venv/bin/pytest` passes (engine, mock-data consistency, report builders).
- `.venv/bin/streamlit run app.py`: every nav page renders without tracebacks. Use Streamlit `AppTest` for each page's smoke test.
- Manual demo run, mock data only and offline: select a title; check score, confidence, interval and decision label; open the map and a state; exclude a comparable and watch the deltas; disable a source and watch confidence change, then re-enable and confirm it returns to base; compare two scenarios; confirm exports are locked until Accept, then download all five and open the PDFs.
- Grep the UI, data and exports for "Delhi NCR" (expect none). Submit form text containing `<script>` and Japanese characters and confirm neither the page nor the PDF breaks.
- Walk the spec's Definition of done checklist item by item.
