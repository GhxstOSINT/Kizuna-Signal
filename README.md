# Kizuna Signal

Kizuna Signal is an explainable pre-release intelligence system for Japanese media entering India. The integration combines the FastAPI backend, persistence and scoring pipeline with a dedicated React and TypeScript dashboard. The previous Streamlit prototype remains in the repository as migration reference only and is not used by the current dashboard or Docker deployment.

## What is implemented

- Versioned FastAPI routes under `/api/v1`
- Projects and title intake
- Persistent analysis jobs and analysis snapshots
- Offline-safe public-signal adapters with provenance and source health
- Content-fit, demand, engagement, comparable and regional scoring
- Confidence calculated separately from market potential
- State-level opportunity ranking
- Explainable positive and negative drivers
- Comparable-title evidence
- Scenario comparison for platform, localization, budget and target regions
- Rule-based launch playbook grounded in model outputs
- PostgreSQL-ready SQLAlchemy models, with SQLite as the zero-setup default
- Docker Compose with PostgreSQL and pgvector
- Automated API and domain tests

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Open:

- API documentation: `http://localhost:8000/docs`
- Readiness: `http://localhost:8000/health/ready`

Run the dedicated website in a second terminal:

```powershell
cd dashboard
npm install
npm run dev
```

Open `http://127.0.0.1:4173`.

## Docker

```powershell
docker compose up --build
```

Open the integrated dashboard at `http://localhost:3000` and the API documentation at `http://localhost:8000/docs`. Override `KIZUNA_DASHBOARD_PORT`, `KIZUNA_API_PORT`, and `KIZUNA_POSTGRES_PORT` when those host ports are already in use.

The website does not fabricate an offline result when the API is unavailable. It shows an explicit recovery state. The backend itself can still operate with its deterministic offline-safe adapters until authenticated live providers and the trained model runtime are supplied.

## Run tests

```powershell
pytest
```

See `docs/TEST_STATUS.md` for backend coverage and verified behavior. Build the dashboard with `npm run build` from `dashboard`.

Refresh the committed API contract after an intentional schema change:

```powershell
python scripts/export_openapi.py
```

Frontend work should fail review if `docs/openapi.json` changes unexpectedly.

## Primary workflow

1. `POST /api/v1/projects`
2. `POST /api/v1/projects/{project_id}/titles`
3. `POST /api/v1/titles/{title_id}/analyses`
4. `GET /api/v1/jobs/{job_id}`
5. `GET /api/v1/analyses/{analysis_id}`
6. `POST /api/v1/analyses/{analysis_id}/scenarios`

`POST /analyses` returns a persistent job. FastAPI executes the current demo pipeline as a background task. The service boundary can later be moved to Prefect or Celery without changing the API contract.

## Stability decisions

- Raw evidence and normalized signals are represented separately in the service contract.
- External sources are isolated behind adapters.
- A failed optional source produces a partial analysis and confidence penalty rather than an invented value.
- Every analysis stores model, feature and scoring versions.
- Every output includes warnings and source status.
- The model is currently a deterministic, explainable baseline intended for integration and UI development. It is not presented as revenue prediction.

## Configuration

Copy `.env.example` to `.env`. Environment variables use the `KIZUNA_` prefix.

## Production evolution

The detailed branch map, verified cross-stack flow, and prioritized remaining work
are maintained in `docs/INTEGRATION_STATUS.md`.

- Replace demo adapters with authenticated API clients and immutable raw-response storage.
- Move background execution to a durable queue.
- Add Alembic-managed migrations before shared deployments.
- Add OIDC authentication and organization-level authorization.
- Add a trained XGBoost model behind the existing scoring interface.
- Add model registry, drift monitoring and partner outcome calibration.

