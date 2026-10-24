# Kizuna Signal: Streamlit prototype

First prototype of the Kizuna Signal dashboard: an explainable pre-release intelligence tool for Japanese
media entering India's regional, multilingual markets. The UI runs on **mock JSON** behind a thin API client
that mirrors the REST routes in the architecture PDF, so a real FastAPI backend can replace it later.

## Run

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
.venv/bin/pytest            # tests
```

Everything works offline. No API keys or live data sources are used.

## Pages

| Page | What it does |
|---|---|
| Portfolio | Title cards with score, confidence, decision, top market; search and format filter |
| New Analysis | Intake form (7 required fields, many optional), completeness meter, staged progress screen. A prototype-only selector simulates normal, partial-data and failure outcomes |
| Results | Tabs: Decision, Regional Intelligence (India map), Comparables, Drivers, Confidence & Sources |
| Scenario Lab | Localization, distribution, geography, release window and budget levers compared with the base strategy |
| Playbook & Export | Launch playbook, human Accept/Reject, then PDF/CSV/HTML exports (locked until accepted) |
| Methodology | Versions, sources, active weights, limitations, session audit log |

Demo path: Portfolio -> *Shadow Bloom* -> Results (score, map, comparables, drivers) -> disable a source on
Confidence & Sources -> Scenario Lab -> Playbook, Accept, export.

## Layout

```
app.py                  entry point (st.navigation, sidebar)
kizuna/api.py           MockApi: method names mirror the PDF's REST routes
kizuna/engine.py        pure scoring / recalculation logic (no Streamlit)
kizuna/intake.py        form fields, validation, completeness
kizuna/state.py         session state: overrides, approvals, audit log
kizuna/charts.py        Plotly figures        kizuna/report.py   PDF / CSV / HTML exports
kizuna/theme.py         CSS and HTML helpers  (all dynamic text is escaped)
views/                  one module per page   sections/   Results tab bodies
data/mock/              config.json + one folder per title (generated, then hand-editable)
data/geo/               India state boundaries (public GeoJSON, prototype only)
scripts/make_mock_data.py   regenerates data/mock (overwrites hand edits)
tests/                  engine, mock data, reports and page smoke tests
```

## Rules the code follows

- Market potential and confidence are always separate outputs.
- Weights, thresholds, decision labels and scenario effects live in `data/mock/config.json`.
- Source toggles, comparable changes and scenarios are overrides on a frozen base analysis; they never change it.
  Every override and approval is written to the audit log.
- Regions with weak evidence are greyed out and not ranked. The region is "Delhi", never "Delhi NCR".
- A recommendation is exported as a launch decision only after an explicit Accept.

## Swapping in the real backend

All views go through `kizuna.api.MockApi`. Implement a client with the same methods (`list_projects`,
`get_analysis`, `get_regions`, `get_comparables`, `get_sources`, `get_scenarios`, `get_recommendation`,
`start_analysis`, `get_job`, ...) that calls the FastAPI endpoints, and return it from `kizuna.state.get_api()`.
The recalculation in `kizuna/engine.py` (source toggles, comparable edits, scenarios) is mocked client-side;
in production those would be server calls such as `POST /analyses/{id}/scenarios`.

## Known limits

- Titles created through New Analysis reuse the closest mock template (a notice is shown on Results).
- Comparables are real titles with made-up performance scores; scenario effects are illustrative.
- PDFs use built-in Latin-1 fonts, so Japanese characters become `?`.
- The state-click on the map relies on Streamlit's plotly selection; the Region dropdown is the fallback.
