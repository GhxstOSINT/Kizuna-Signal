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
