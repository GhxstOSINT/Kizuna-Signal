# Platform architecture

## Stable hackathon boundary

```text
Web dashboard
    |
    | JSON over REST /api/v1
    v
FastAPI application
    |-- project/title intake and validation
    |-- analysis and job orchestration
    |-- scenario API
    |-- health/readiness and OpenAPI
    |
    +--> source adapter boundary
    |      |-- Google Trends signal
    |      |-- YouTube engagement signal
    |      |-- Wikimedia attention signal
    |      |-- AniList metadata/community signal
    |      `-- India regional-context signal
    |
    +--> feature and comparable-title layer
    +--> explainable scoring and confidence layer
    +--> regional opportunity and recommendation layer
    `--> SQLAlchemy persistence
           |-- SQLite for zero-setup local demo
           `-- PostgreSQL/pgvector through Docker Compose
```

The system is a modular monolith. This is deliberate: three people can understand, run and debug one deployable service during the hackathon, while adapter and service boundaries allow later extraction.

## Domain boundaries

- `api/routes`: HTTP contract only; no scoring formulas.
- `schemas`: validated request/response contracts used by backend and frontend.
- `services/sources`: isolated evidence providers. A provider failure must return unavailable evidence, never a fabricated observation.
- `services/comparables`: retrieves semantically relevant reference titles.
- `services/scoring`: normalized components, weighted score, regional scoring and drivers.
- `services/confidence`: evidence coverage/quality/freshness and uncertainty interval.
- `services/recommendations`: interpretable launch playbook.
- `services/scenarios`: deterministic what-if comparison.
- `db`: persistence models and session lifecycle.

## Scoring contract

The overall market-potential score is a weighted combination of content fit, demand momentum, regional opportunity, engagement quality and comparable performance. Weight definitions are code-owned and versioned. Confidence is stored separately so a high score with weak evidence is visibly different from a high-confidence opportunity.

Every completed analysis stores:

- immutable output snapshot;
- source status, warnings and provenance;
- model, feature and scoring versions;
- explainable positive/negative drivers;
- a confidence interval;
- the associated job lifecycle.

## Failure model

- Invalid user input: reject with `422` before work starts.
- Unknown resource: `404`.
- Analysis still running: `409` when its result is requested.
- Optional source unavailable: complete partially, reduce confidence, retain warnings.
- Pipeline exception: mark both analysis and job failed with an error field.
- Database unavailable: readiness fails so the platform can stop routing traffic.

## Deployment profiles

**Local demo:** SQLite, in-process background tasks, deterministic adapters. This runs without API keys or internet and guarantees a reproducible judging demo.

**Shared hackathon environment:** Docker Compose, PostgreSQL/pgvector and the same API. Add live API credentials only through environment variables.

**Post-hackathon:** durable worker queue, Alembic migrations, OIDC/RBAC, object storage for raw evidence, encrypted secrets, rate limiting, tracing, model registry, drift monitoring and partner-outcome calibration.

## Data ethics and evidence rules

- Use licensed, public, partner-provided or explicitly permitted data only.
- Preserve source timestamps and provenance.
- Do not infer protected personal attributes or score individuals.
- Do not present public attention proxies as revenue, retention or platform viewing data.
- Keep partner-commercial metrics segregated and access-controlled when introduced.
