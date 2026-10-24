# Cross-branch integration status

## Connected branch histories

The `integration` branch contains all current repository histories:

- `Initail-API-Layer`: original API foundation and architecture PDF.
- `backend`: tested FastAPI, persistence, scoring, confidence, scenarios, documentation and CI.
- `frontend`: initial Streamlit setup.
- `feature/1st-prototype-streamlit-ui`: complete dashboard prototype, mock data, reports and UI tests.

The feature branch already descends from `frontend`; `backend` already descends from `Initail-API-Layer`. Merging the feature branch into `integration` therefore connects all four histories without force-pushing or modifying contributor branches.

## Working full-stack path

1. Streamlit submits its intake form through `BackendApi`.
2. The adapter creates a backend project and title using `/api/v1/projects`.
3. It starts `/api/v1/titles/{title_id}/analyses`.
4. The progress screen polls `/api/v1/jobs/{job_id}`.
5. Completed backend results are translated into the dashboard view contract.
6. Portfolio, decision, regional, comparable, driver, confidence, source and playbook screens render the backend analysis.
7. `KIZUNA_FRONTEND_MODE=auto` uses the backend when ready and falls back to deterministic mock data when it is unavailable.
8. Docker Compose starts PostgreSQL, FastAPI and Streamlit together.

Backend values remain authoritative for the base market score, confidence, interval, classification and recommendation.

## Deliberately preserved fallback

The mock dataset remains because it provides:

- an internet-independent judging path;
- seeded portfolio examples;
- repeatable screenshots and presentation data;
- frontend development when the API is stopped;
- simulated failure screens that the current in-process backend cannot reliably trigger on demand.

## Remaining integration work

### P0 before final judging

- Replace the Scenario Lab's local lever simulation with `POST /api/v1/analyses/{analysis_id}/scenarios` and map saved scenario results back to the cards.
- Move source toggles and comparable-set overrides to backend endpoints. They are disabled for live sources today, while comparable changes still run in the prototype engine.
- Add a visible UI badge showing Live API versus Offline Demo mode.
- Rehearse Docker Compose on the final presentation machine and seed at least one completed live-backend title.
- Run the complete Streamlit suite in GitHub Actions; the local Python 3.12 verifier could not install the frontend dependencies because package index requests timed out, while CI uses standard Linux Python.
- Confirm the GitHub Actions workflow and both container builds are green.

### P1 platform hardening

- Replace deterministic source adapters with recorded-fixture-tested AniList, Wikimedia, YouTube and trends adapters.
- Add a durable worker queue so jobs survive API restarts.
- Add Alembic migrations for the current consolidated schema.
- Add request idempotency for repeated Analyze clicks.
- Add authentication, organization/project authorization and audit persistence.
- Add pagination and a direct `GET /titles/{id}` endpoint to avoid portfolio-wide scans.
- Persist approvals and audit history; they currently live in Streamlit session state.
- Store generated exports and expose a backend report endpoint.

### P1 data/model validation

- Store immutable raw evidence with timestamps, geography, licensing and provenance.
- Replace neutral missing-metric defaults with explicit imputation or weight renormalization.
- Enforce the pre-release cutoff to prevent post-release leakage.
- Build a historical outcome dataset and report ranking, calibration and error metrics.
- Expand regional evidence beyond the current eight backend state profiles.
- Replace the embedded comparable catalogue with versioned retrieval and reviewed reference data.

### P2 production readiness

- Add Redis/worker monitoring, tracing, rate limiting and alerting.
- Add PostgreSQL migration, backup/restore and concurrency tests.
- Add accessibility, browser and responsive E2E testing.
- Add deployment environments, managed secrets, TLS and rollback procedures.

## Current definition of connected

The branches are structurally connected and the core intake-to-result journey crosses the real HTTP contract. The product is not yet fully backend-authoritative for analyst overrides, scenarios, approvals or exports; those are the principal remaining integration seams.
