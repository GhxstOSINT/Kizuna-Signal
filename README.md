# Kizuna Signal

Explainable pre-release intelligence for Japanese media entering India. See
`Kizuna_Signal_Complete_Product_Architecture.pdf` for the full architecture.

## Setup
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
docker compose up -d
```

## Database
Enable pgvector once, then create the first migration:
```
docker compose exec postgres psql -U kizuna -c "CREATE EXTENSION IF NOT EXISTS vector;"
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```
Add `from pgvector.sqlalchemy import Vector` to the generated migration if missing.

## Run
```
uvicorn app.main:app --reload
```
Health: http://localhost:8000/health  |  Docs: http://localhost:8000/docs

## Test
```
pytest
```

## Layout
- `app/api/routes`: thin routers; `app/services`: logic; `app/schemas`: request/response validation
- `app/db/models`: tables; `app/db/session.py`: engine and session
- Scope here: database, application and API layers. ML, ingestion and UI are added later.

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
