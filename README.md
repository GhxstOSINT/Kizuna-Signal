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

The model-training scripts in `scripts/` are optional and not needed to run the API or the tests. They need the extra dependencies: `python -m pip install -e ".[ml]"`.

The survey source defaults to simulated data in `data/synthetic/` (rows labelled `PROXY synthetic`); see `data/synthetic/README.md` and set `KIZUNA_SURVEY_DIR=data/survey` to use only real rows.

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



# ML layer (state model, /predict, reports)

## AniList dataset (ML prep)
```
python scripts/build_anilist_dataset.py --pages 20 --start-year-from 2000
```
Raw responses go to `data/raw/anilist` (append-only, checksummed, cached 7 days). Output in `data/processed`: `anilist_features.jsonl` (pre-release features only), `anilist_labels.jsonl` (popularity outcomes, joined by `anilist_id`) and `anilist_report.json` (drop counts). Outcomes never appear in the feature table.

## India state-level model (initial training)
```
python scripts/build_anilist_dataset.py --pages 6 --sort popularity --start-year-from 2016 --start-year-to 2023
python scripts/collect_trends.py --n-titles 150 --max-requests 200   # resumable; repeat daily
python scripts/train_initial.py --n-titles 100
```
Writes `models/<version>/{report.json,model.joblib}` and `models/initial_report.json`. Sentence Transformers are used when installed, otherwise TF-IDF+SVD (`--embedder`). Engagement quality (YouTube) is not collected yet.

## State model and analysis worker

The state model predicts where a title over-performs across India's states and UTs. One task per
model package (`models/state/`); SEO and other tasks get their own, never this one.

```
python scripts/train_state_model.py     # trains from csv/ (see csv/data_dictionary.csv); saves models/state/<version>/
python scripts/run_worker.py --once     # runs queued analyses with models/state/LATEST.json
```

* Target is `lift` (the dictionary's recommended label), not raw share: raw share is dominated by each
  state's baseline. State and grand means are recomputed from training titles only.
* Features: genres, tags (>=10 titles), format, season/year, sequel flag, length, region zone and language,
  pre-release Trends demand, and history from earlier titles whose 52-week label window had ended
  (same franchise, same studio, similar synopsis). Global popularity/score are never loaded.
* Metrics, blend weight and intervals come from out-of-fold predictions; final models are refit on all titles.
* `POST /titles/{id}/analyse` queues the job; the worker fills `Analysis` and per-state `RegionalScore` rows
  (`score` = predicted lift, ranked high to low; `evidence` has the expected share and interval).
  `market_potential` stays empty.
* States with no Trends geo (Ladakh) are not scored. States with under 10 training titles raise `sparse_state_training`.

## SEO routes and worker (v0)

`POST /api/v1/titles/{id}/seo` (Idempotency-Key supported) queues a job; `GET /api/v1/titles/{id}/seo` returns the
latest result (404 never requested, 409 not finished). Candidate terms come from the title names plus
dubbing languages in the assumptions; each is measured against Google Trends for India and ranked.
When a state analysis exists, the best term is also measured in the top three states.

This is measurement, not a trained model: there is no labelled SEO outcome in the data. It returns relative
interest only (no search volume, keyword difficulty, rankings or launch timing; see `not_available`).

`scripts/run_worker.py` now runs state analyses, SEO jobs and `/sources/collect` jobs. Collection works for
`google_trends`; other sources are recorded as `unavailable` with `no_adapter_for_database_titles`.
`tests/test_e2e_postgres.py` exercises all routes against a throwaway database on the docker-compose Postgres.

## One-shot prediction

`POST /api/v1/predict` takes a title and returns the state-by-state prediction in one response (no project,
title row or job). Fields: `name_en`, `genres`, `synopsis` (50+ chars), optional `tags`, `studio`, `release_date`,
`episodes`, `languages`, `localization_mode`, `include_seo` (live Trends, slow). Response: `india` (confidence,
warnings, top/bottom states), `states` (rank, lift, 80% interval, expected share, drivers), `comparables`, `seo`.
It loads `models/state/LATEST.json` once; restart the API after retraining. There is no single national score.

## India success score and reports

`/predict` now also returns `success`: the architecture's Market Potential, 0-100 where 50 is a typical anime in the
training set (not a revenue forecast). `S = sum(w_i c_i) / sum(w_i)` over components that are measured **and validated**
(weights in `app/ml/scoring_config.py`; maths in `app/ml/success.py`).

| Component (weight) | Status for an unreleased title |
|---|---|
| Regional opportunity (20%) | measured: `100 * Phi(sum_s share_s * lift_s / sigma)` from the state model |
| Content fit (25%), comparable performance (15%) | measured against global popularity (the only outcome in csv/), shown but excluded when held-out Spearman < 0.1 |
| Demand momentum (25%), engagement quality (15%) | unavailable (no pre-release Trends window; no YouTube adapter) |

`POST /api/v1/predict/report?format=pdf|json|csv|xml` takes the same body as `/predict` and returns a download:
PDF (summary, India tile map, state ranking with intervals, shares and comparables, worked mathematics, evaluation and
limitations; matplotlib only), JSON (full report), CSV (one row per state, title scores repeated), XML (same content as JSON).
The stored-title route works too: `POST /api/v1/reports {"analysis_id", "format": "pdf|json|csv|xml"}` queues a job,
`scripts/run_worker.py` renders it into `data/reports/` (`REPORTS_DIR`), and `GET /api/v1/reports/{id}/download` serves
the file (409 until it is rendered). Stored titles have no tags or episode count, so those features are empty there.
Every renderer reads one dict built by `app/reports/build.py`. The report also lists `limitations` and model evaluation.

## Synthetic fill for sparse states, model card

Google Trends returns nothing for most titles in small states (Lakshadweep: 10 of 62 titles), so those states rest on
few, selected rows. `app/ml/synthetic.py` fills each missing title x state cell with a weighted average of (a) the lift
of the most similar training titles that have data in that state and (b) the title's own lift in states sharing its
language/zone, shrunk towards 0 by `n/(n+k)`; thinly supported cells are skipped. Synthetic rows train at weight 0.3,
are built from training-fold titles only, never validate, and never feed history features.

```
python scripts/train_state_model.py                 # synthetic on (default); --no-synthetic, --synthetic-weight 0.5
python scripts/model_report.py                      # results/MODEL_REPORT.md, state_coverage.csv, 08_*.png, 09_*.png
```
`GET /api/v1/model` returns the model card (data counts, held-out accuracy with and without synthetic rows, per-state
real/synthetic coverage and held-out bias, success-model validation). `/predict` states carry `synthetic_rows`; the
`synthetic_augmented` warning and an extra limitation appear when the model used them. The PDF evaluation page shows the
with/without comparison.

The India success score's content-fit and comparables now learn from all 300 titles in `csv/` (global popularity needs
no state labels), not the 62 state-labelled ones: content-fit held-out Spearman -0.34 -> 0.39, so 60% of the score weight
is counted instead of 20%.
