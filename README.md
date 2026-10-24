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

The state model predicts how a title's India demand splits across states and UTs. It is one task
per model package (`models/state/`); SEO and other tasks get their own, never this one.

```
python scripts/train_state_model.py     # trains on every labelled title; saves models/state/<version>/
python scripts/run_worker.py --once     # runs queued analyses with models/state/LATEST.json
```

* Encoder fitted on all AniList titles; comparables from every earlier, other-franchise labelled title.
* Metrics, blend weight and intervals come from out-of-fold predictions; final models are refit on all titles.
* `POST /titles/{id}/analyse` queues the job; the worker fills `Analysis` and per-state `RegionalScore` rows
  (`score` = predicted share x number of states, so 1.0 is average). `market_potential` stays empty.
* States with no Trends geo (Ladakh) are not scored. States with under 10 training titles raise `sparse_state_training`.
