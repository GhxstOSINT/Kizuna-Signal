# Kizuna Signal Backend

Kizuna Signal is an explainable pre-release intelligence system for Japanese media entering India. This repository contains the API, persistence model, deterministic offline demo pipeline, confidence calculation, comparable-title retrieval, scenario simulation and launch recommendation logic.

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

## Docker

```powershell
docker compose up --build
```

## Run tests

```powershell
pytest
```

The integration gate currently contains 140 automated tests with 95% application line coverage. See `docs/TEST_STATUS.md` for the verified behaviors and the production-only gaps that are intentionally not claimed as passing.

The model-training scripts in `scripts/` are optional and not needed to run the API or the tests. They need the extra dependencies: `python -m pip install -e ".[ml]"`. The trained models are not used by the app yet (see `docs/DATA_SOURCES.md`).

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

- Replace demo adapters with authenticated API clients and immutable raw-response storage.
- Move background execution to a durable queue.
- Add Alembic-managed migrations before shared deployments.
- Add OIDC authentication and organization-level authorization.
- Add a trained XGBoost model behind the existing scoring interface.
- Add model registry, drift monitoring and partner outcome calibration.

