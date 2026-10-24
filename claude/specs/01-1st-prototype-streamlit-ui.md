# Spec: 1st Prototype Streamlit UI

## Overview
A Streamlit dashboard for Kizuna Signal, the explainable pre-release intelligence engine for Japanese media entering India (`Idea/Kizuna_Signal_Complete_Product_Architecture.pdf`). It walks an analyst through one decision: *should we launch this Japanese title in India, and if so where and how?* The flow is title input, evidence, forecast, explanation, scenario and launch action. This is the throw-away-friendly first prototype, built for the hackathon's deterministic four-minute demo. It runs entirely on mock JSON through a thin API-client layer, so the real FastAPI backend (PDF section 04) can replace it later without UI rewrites. Layout, tech stack and screens are expected to change, so everything is modular and config-driven.

## Depends on
- None in code (the repo contains only `requirements.txt`, `.gitignore`, `data/geo/india_states.geojson` and the gitignored `Idea/` PDF).
- Backend contract: the PDF's REST routes (section 04). The mock client mirrors them but does not call them.

## Interfaces
No HTTP routes are added. UI screens (Streamlit `st.navigation` pages, no auth in this prototype):

- **Portfolio** (`views/portfolio.py`): landing page. Title cards (poster placeholder, title, score, confidence, decision, top state, primary language, platform, last analysis date, status), search, content-format filter, "Analyse New Title" button, and the empty state.
- **New Analysis** (`views/new_analysis.py`): intake form, then the progress screen.
  - Required: title, synopsis, content format, primary genre, source material, expected release period, target platform (or "Undecided").
  - Optional: alternative/English title, poster upload, trailer URL, secondary genres, themes, studio, director, cast, episode count/duration, age rating, franchise status, target languages, target states, budget band, release month, intended audience, partner CSV (marked "coming later", disabled).
  - A completeness indicator is shown in the form.
  - Progress screen: pipeline stages with ticks, a per-source status list, and partial-data, error (Retry / Use Cached Data) and complete states.
  - Prototype-only "Simulate backend outcome" selector: Normal / Partial data / Failure.
- **Results** (`views/results.py`): tabs for Decision, Regional Intelligence, Comparables, Drivers, and Confidence & Sources.
  - Decision: header with score, confidence, interval, decision label and recommendation line, plus the component breakdown.
  - Regional Intelligence: India choropleth, ranked states, language affinity, click or select a state for its detail panel.
  - Comparables: five default cards, include/exclude controls, expected/optimistic/conservative sets, and live deltas.
  - Drivers: positive and negative SHAP-style points with a per-driver "Why?" popover.
  - Confidence & Sources: factor bars, warnings, and source health with enable/disable toggles that trigger recalculation.
- **Scenario Lab** (`views/scenario_lab.py`): lever controls (localization, distribution, geography, release month, marketing budget), base-vs-scenario comparison with score, confidence, cost and reach deltas, and a recommended option. Two preset scenarios plus a custom one.
- **Launch Playbook & Export** (`views/playbook_export.py`): playbook, per-recommendation objects (decision, expected benefit, evidence, confidence, principal risk), human approval (Accept / Reject with name and reason), and exports.
  - Exports: one-page executive brief PDF, full analysis PDF, regional CSV, India-map interactive HTML, scenario summary CSV.
  - A mock "read-only share link" is shown but not functional.
  - Accept is required before a recommendation is marked as an exported "launch decision".
- **Methodology** (`views/methodology.py`): sources and licences note, model/config/feature-snapshot versions, active scoring weights, limitations, audit log of this session's overrides and approvals.

Programmatic interface: `kizuna/api.py` exposes `MockApi` with methods named after the PDF routes: `list_projects`, `get_title`, `start_analysis` (returns a job id), `get_job`, `get_analysis`, `get_regions`, `get_comparables`, `get_sources`, `get_scenarios`, `get_recommendation`. All views must go through it. Access: none (local prototype).

## Data changes
No database. Files only:
- `data/mock/config.json`: scoring components, weights, optional-component flag, decision thresholds, confidence-factor weights, evidence threshold for suppressing a state, language list, state-to-language/audience mapping, scenario lever effects, pipeline stage names.
- `data/mock/projects.json`: portfolio index.
- `data/mock/<title_id>/{title,analysis,regions,comparables,sources,scenarios,recommendation}.json` for 3 titles:
  1. high-confidence (reference: *Shadow Bloom*, score about 78, confidence about 82)
  2. low-confidence (score about 81, confidence about 43, "Insufficient evidence")
  3. partial-data (one source unavailable)
- `data/geo/india_states.geojson` already exists (36 regions, key `properties.ST_NM`, includes `Delhi`). Region names in the mock JSON must match it exactly.
- Runtime state (source toggles, comparable overrides, approvals, audit log, newly created projects) lives only in `st.session_state`. Nothing is persisted.

## UI / Templates
- **Create:** `.streamlit/config.toml` (light theme, accent colour), `kizuna/theme.py` (shared CSS, badges, cards; all user-entered text HTML-escaped), the `views/*.py` pages and `sections/*.py` tab renderers listed below.
- **Modify:** none (greenfield).
- Design rules (from the PDF and team suggestion):
  - Score and confidence are always separate visuals.
  - Never show a score without a decision label.
  - Weak-evidence states are greyed on the map and excluded from ranking, with an explicit reason.
  - A "Baseline model" badge appears when the fallback model ran.
  - The five primary components (Content Fit 25%, Demand Momentum 25%, Regional Opportunity 20%, Engagement Quality 15%, Comparable Performance 15%) are always shown.
  - "Localization Readiness" is optional: it is shown only when the sidebar "Show optional components" toggle is on and carries weight 0.
  - The region is "Delhi", never "Delhi NCR". City names (Mumbai, Bengaluru) appear only in playbook text.

## Files to change
None (greenfield). `requirements.txt` and `.gitignore` already exist; only append `pytest` to `requirements.txt` (see New dependencies).

## Files to create
- `app.py`: entry point; sets page config, builds `st.navigation`, shared sidebar (active title picker, optional-components toggle).
- `kizuna/__init__.py`
- `kizuna/config.py`: paths and constants.
- `kizuna/api.py`: `MockApi` and `get_api()`.
- `kizuna/engine.py`: pure functions that recalculate the view from the frozen base analysis plus overrides: component scores, overall score, confidence, interval, decision label, deltas, suppression of weak states, scenario simulation. No Streamlit imports.
- `kizuna/state.py`: session-state helpers: overrides, approvals, audit log, created projects.
- `kizuna/theme.py`: CSS and HTML component helpers.
- `kizuna/charts.py`: Plotly figures: component bars/radar, choropleth, SHAP bars, scenario comparison.
- `kizuna/report.py`: PDF (fpdf2), CSV and HTML export builders (Latin-1-safe text sanitising).
- `views/portfolio.py`, `views/new_analysis.py`, `views/results.py`, `views/scenario_lab.py`, `views/playbook_export.py`, `views/methodology.py`
- `sections/decision.py`, `sections/regions.py`, `sections/comparables.py`, `sections/drivers.py`, `sections/confidence.py`: Results tab bodies.
- `scripts/make_mock_data.py`: deterministic generator that writes the mock JSON; afterwards the JSON is the source of truth and may be hand-edited.
- `data/mock/**`: files listed under Data changes.
- `.streamlit/config.toml`
- `tests/test_engine.py`, `tests/test_mock_data.py`, `tests/test_report.py`
- `README.md`: how to run, folder map, and how to swap `MockApi` for the real REST client.

## New dependencies
- Runtime (already in `requirements.txt`): `streamlit`, `plotly`, `pandas`, `fpdf2`.
- Dev: `pytest` (the PDF's stack lists Pytest).
- No others. Do not add kaleido; the map export is HTML.

## Out of scope
- The real FastAPI backend, database, Redis, MinIO, auth, roles, multi-user isolation.
- Live calls to Google Trends, YouTube, Wikimedia, AniList or Census, and any model training or inference (SHAP, XGBoost, embeddings).
- Retraining on scenario changes, partner data import, a real read-only share link.
- Real asynchronous jobs (the progress screen is simulated with short sleeps).
- Persistence across sessions, Docker, CI, observability.
- A React/Next.js frontend and any final visual design.
- Real file/PDF validation or malware scanning of uploads.

## Rules for implementation
- Follow the existing patterns and layering of the surrounding code. The repo is greenfield, so use this spec's layout. Pages call `kizuna.api` only. `kizuna.engine` stays pure and testable. Views contain presentation only.
- Keep the UI thin and mirror the PDF's architecture principles: all scoring and recalculation logic lives in `engine.py` and `api.py`, never inline in views.
- Never fabricate data at runtime. Unavailable sources are shown as unavailable and reduce confidence. The mock JSON is the only data source.
- Keep potential and confidence separate everywhere (UI, exports, API payloads).
- Scoring weights, thresholds, lever effects and decision labels come from `data/mock/config.json`, not code.
- Disabling a source or excluding a comparable never mutates the base analysis. It is an override on the frozen snapshot, recomputed by `engine.py`, and logged to the audit log (user, time, previous value, new value, reason when applicable). At least 2 comparables must stay included.
- A recommendation can be marked accepted or exported as a "launch decision" only after an explicit human Accept.
- Validate and safely handle all untrusted input. Escape all user-entered text before it goes into `unsafe_allow_html` markup. Sanitise text for PDF output. Check required form fields and ranges, and cap upload size and type for the poster (image only).
- No credentials, API keys or secrets in the repo. Mock data uses fictional titles for the unreleased title. Comparable titles are real historical titles with illustrative mock scores only.
- No new dependencies unless listed above. Keep changes scoped to this spec and do not touch `Idea/`.
- Add or update tests, and update `README.md` with the run instructions and the page list.

## Definition of done
- [ ] `pip install -r requirements.txt` then `streamlit run app.py` starts with no errors or Python tracebacks, and every page in the nav renders.
- [ ] Portfolio shows 3 mock title cards with score, confidence, decision label, top state, language and platform. Search and format filter work, and "Analyse New Title" opens the form.
- [ ] New Analysis blocks submit until all 7 required fields are valid and shows a completeness indicator. A valid submit runs the staged progress screen, then lands on Results.
- [ ] "Simulate backend outcome" works: Partial data shows the partial-data banner and reduced confidence, and Failure shows the error state with working Retry and Use Cached Data actions.
- [ ] Results Decision tab: score, separate confidence with interval, decision label and recommendation line are shown. The 5 primary components are displayed. "Localization Readiness" appears only with the optional toggle.
- [ ] The weighted sum of component scores equals the displayed market potential (verified by `tests/test_engine.py`).
- [ ] The map colours all 36 regions from `india_states.geojson`. States below the evidence threshold are grey and excluded from the ranking with a visible reason. The top 3 and the ranked list are shown. Selecting a state shows its detail panel with reasons. "Delhi" appears and "Delhi NCR" appears nowhere in the UI, mock data or exports.
- [ ] Comparables: 5 cards by default with similarity and reasons. Include/exclude and set switching update score and confidence immediately. Excluding below 2 is blocked with a message. Each change is audit-logged.
- [ ] Drivers show positive and negative points with a working "Why?" per driver. Drivers whose only sources are disabled are shown as inactive.
- [ ] Disabling a source on the Confidence & Sources tab recalculates confidence (and the score where defined) and displays the delta against base. An unavailable source cannot be re-enabled. Re-enabling restores the base values exactly.
- [ ] Scenario Lab: two presets and a custom scenario each show score, confidence, cost and reach deltas versus base, and a recommended option with a rationale. The base analysis is unchanged afterwards.
- [ ] The low-confidence title (score about 81, confidence about 43) shows "Insufficient evidence" with a prominent low-confidence message instead of a launch recommendation.
- [ ] Playbook page: the recommendation objects show decision, benefit, evidence, confidence and risk. Export buttons are disabled until Accept is clicked. After Accept, the executive-brief PDF, full PDF, regional CSV, map HTML and scenario CSV all download and open. The PDFs include assumptions, score, confidence, regional ranking, comparables, drivers, recommendation, data limitations, and sources/model/config versions.
- [ ] Methodology page lists the sources, versions, active weights, limitations and the audit log of overrides and approvals from the current session.
- [ ] User-entered text containing HTML or non-Latin characters (e.g. `<script>`, Japanese) does not break the page or the PDF export.
- [ ] A full demo run (portfolio, select title, results, map, comparables, drivers, disable source, scenario compare, export) completes with only mock data, with no network access, in under four minutes.
- [ ] `pytest` passes for the engine (weights, confidence, interval, decision labels, source toggle round-trip, comparable exclusion, scenario simulation), the mock-data schema/consistency (state names match the GeoJSON, weights sum to 100, no "Delhi NCR"), and the report builders.
- [ ] `README.md` documents run steps, folder map, mock-data regeneration, and where to replace `MockApi` with the real REST client.
