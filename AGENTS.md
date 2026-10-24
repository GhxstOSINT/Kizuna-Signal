# Kizuna Signal: map for agents and new contributors

Explainable pre-release market intelligence for Japanese media entering India. Read this first;
`README.md` has the product overview and `docs/README.md` indexes the deeper docs.

## Where things live

| Task | Go to |
|---|---|
| Add or change an API route | `backend/app/api/routes/`, schemas in `backend/app/schemas/` |
| Scoring, confidence, scenarios, playbook (rule-based analysis) | `backend/app/services/` |
| An evidence source (AniList, Trends, Wikimedia, YouTube, survey) | `backend/app/services/sources/` (provider plug-ins) and `backend/app/adapters/` (raw collectors that cache to `data/raw/`) |
| Database models and session | `backend/app/db/` |
| Settings, errors, logging, **filesystem paths** | `backend/app/core/` |
| State model, `/predict`, success score | `backend/app/ml/` (map in its `__init__.py`), served by `backend/app/api/routes/predict.py` |
| PDF/JSON/CSV/XML reports | `backend/app/reports/` |
| Train a model, build a dataset | `backend/scripts/train/`, `backend/scripts/data/` |
| Backend tests | `backend/tests/`, mirroring `app/`: `api adapters contract e2e integration ml reports unit` |
| A page, component or API call in the dashboard | `frontend/src/pages/`, `components/`, `api/` |
| Dashboard styles | `frontend/src/styles/`, one file per page area; `index.css` fixes the order |
| Training tables, survey data, research evidence | `data/` |
| Trained models | `models/state/<version>/`, latest named in `models/state/LATEST.json` |
| API contract snapshot | `docs/openapi.json` |
| Old Streamlit prototype | `legacy/streamlit/`, reference only |

## Commands (from the repository root)

```bash
python -m pip install -e "backend[dev,ml]"          # Python 3.11+, pandas must stay < 3
uvicorn app.main:app --app-dir backend --reload      # API on :8000, docs at /docs
pytest backend                                       # all backend tests, coverage gate is 90%
ruff check backend/app backend/tests backend/scripts && ruff format --check backend/app backend/tests backend/scripts
python backend/scripts/dev/export_openapi.py         # after any schema/route change; CI fails on drift
cd frontend && npm ci && npm run dev                 # dashboard on :4173, proxies /api to :8000
cd frontend && npm run build                         # tsc + vite build
docker compose up --build                            # API + dashboard + PostgreSQL
```

## Rules that are easy to break

- **Do not move or rename `backend/app/ml/{state_model,features,models,embeddings,intervals}.py`.**
  Saved models are pickles that store those import paths; renaming breaks every `model.joblib`,
  including ones trained outside this repo.
- **Never build paths from the working directory.** Use `app.core.paths` (`REPO_ROOT`, `DATA_DIR`,
  `TABLES_DIR`, `MODELS_DIR`, `REPORTS_DIR`). Folder settings in `Settings` (`models_dir`,
  `csv_dir`, `survey_dir`, ...) are resolved against the repo root; set `KIZUNA_ROOT` to override
  (the Docker image does).
- **`docs/openapi.json` is the frontend contract.** Regenerate it deliberately; an unexpected diff
  should fail review.
- **Survey data:** `data/survey/` holds no real rows by design. The default `KIZUNA_SURVEY_DIR` is
  `data/synthetic/`, rows labelled `PROXY synthetic`. Never copy synthetic rows into `data/survey/`.
- **`data/training/` models are experiments**, not the production models, and are not wired into
  `backend/app/`. The real models live in `models/state/`.
- **Post-release outcomes are never features.** Keep leakage guards in `app/ml` intact.
- In `frontend/src/styles/`, file order in `index.css` is the CSS cascade; `responsive.css` and
  `mobile-polish.css` must stay last.
- The Streamlit entry file is `legacy/streamlit/streamlit_app.py`, not `app.py`: a top-level
  `app.py` would shadow the backend's `app` package.

## Testing notes

- Backend tests run from any directory. Tests that need a trained model skip if
  `models/state/LATEST.json` is absent; one is committed, so they normally run.
- Legacy tests are separate: `cd legacy/streamlit && pytest`.
