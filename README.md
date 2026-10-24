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
