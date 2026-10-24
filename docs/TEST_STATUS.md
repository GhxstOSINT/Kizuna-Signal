# Test implementation status

This document maps the comprehensive test library to what is executable in the current hackathon backend. It deliberately separates tested behavior from planned production behavior.

## Automated now

- Liveness and database readiness metadata
- Controlled readiness failure on database error
- Secret-free health and source-health responses
- Allowed/disallowed CORS origins and non-browser access
- Valid OpenAPI generation and committed snapshot equality
- Versioned business routes
- Stable confidence, source-status and decision-classification enums
- Unified JSON error envelope for 404, 405, 409 and 422
- Malformed JSON handling
- Strict unknown-field and wrong-type rejection
- Golden Unicode project/title round trip
- Synopsis length boundary at 39/40 characters
- ISO-8601 UTC timestamps with `Z`
- Complete analysis result contract
- Market score bounds and weighted-formula invariant
- Confidence separated from score
- Regional scores, comparables, drivers and recommendation
- Partial completion and confidence penalty when a source is unavailable
- Monotonic, bounded job progress
- Controlled 409 before a result exists
- Scenario creation, persistence and base-analysis immutability
- Deterministic repeated analysis with the same fixture and versions
- Offline golden demo and partial-source demo
- Live-source failure modes (Wikimedia, YouTube, AniList, Google Trends): timeouts, non-JSON bodies, JSON of the wrong shape and missing fields each yield an unavailable source with no metrics and no internal exception text in the warnings
- A crashing analysis or adapter exposes only a fixed public message; details stay in the server log

## P0 blocked by components not implemented yet

- Post-release leakage enforcement: requires timestamped raw evidence and a feature cutoff model.
- PostgreSQL integration tests: Docker configuration exists, but CI/service provisioning is not yet wired.
- Frontend polling, refresh recovery and generated-TypeScript compilation: require the frontend repository.
- Duplicate-click idempotency under concurrency: requires an idempotency key or database uniqueness strategy.
- Durable restart/recovery tests: require an external worker queue rather than in-process background tasks.
- Authentication and organization isolation: authentication/RBAC is intentionally not part of the current demo build.

These items must not be reported as passing until their underlying capabilities exist.

## Commands

```powershell
pytest
pytest -m "unit or api or contract"
pytest -m "integration or e2e"
pytest --cov=app --cov-report=term-missing
python scripts/export_openapi.py
ruff check app tests scripts
ruff format --check app tests scripts
```

## Current verified baseline

- Tests: 140 passing
- Application line coverage: 95%
- Static quality check: passing
- OpenAPI snapshot: committed at `docs/openapi.json`
- Golden mode: deterministic and independent of live credentials
- CI: lint, format, OpenAPI diff, 90% coverage gate and container build configured
