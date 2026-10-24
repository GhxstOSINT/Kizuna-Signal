# Backend

FastAPI service (`/api/v1`), the rule-based analysis pipeline, and the ML layer. Python 3.11+.
Commands are run from the repository root; see `../AGENTS.md`.

```
app/
  main.py          FastAPI app, middleware, error handlers
  api/             router.py and routes/ (projects, analyses, sources, health, model, predict)
  schemas/         Pydantic request/response models; enums.py holds the shared vocabularies
  services/        rule-based pipeline: analysis, scoring, confidence, comparables, regional,
                   recommendations, scenarios; model_analysis bridges to the trained model
    sources/       evidence providers behind one interface (registry, demo, anilist, google_trends,
                   wikimedia, youtube, regional_context)
  adapters/        raw collectors with on-disk caching (AniList, Google Trends)
  ml/              state model, success score, features (see its __init__.py)
  reports/         report dict (build.py) and the json/csv/xml/pdf renderers
  seo/             search-term candidates and Google Trends ranking
  db/              SQLAlchemy models and session
  core/            config.py (Settings), paths.py (repo-root anchors), errors.py, logging.py
  data/            packaged static data (Census 2011 states)
tests/             mirrors app/: unit api adapters contract integration e2e ml reports;
                   support/ has shared helpers, fixtures/ has sample payloads
scripts/
  train/           train_state_model, train_initial, train_title_model, train_regional_model, model_report
  data/            dataset builders and collectors (AniList, Trends, survey, synthetic survey, regions)
  dev/             export_openapi, demo_flow, setup.ps1, start.ps1
```

## Two layers, one API

1. **Analysis pipeline**: `POST /projects`, `/titles`, `/analyses` store records, run a background
   job over the registered sources and persist a scored result (`services/analysis.py`).
2. **ML layer**: `POST /predict` and `/predict/report` run the saved state model without storing
   anything. `GET /model` returns its model card. The model is read from `models/state/LATEST.json`
   and cached; restart the API after retraining.

## Configuration

`app/core/config.py` (`KIZUNA_` environment variables, `.env` at the repo root). Folder settings are
relative to the repository root, not the working directory.

## Tests

```bash
pytest backend                    # from the repo root, or `pytest` inside backend/
pytest backend/tests/unit -m unit
```
