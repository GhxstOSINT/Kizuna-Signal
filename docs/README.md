# Docs index

| File | What it is |
|---|---|
| `PLATFORM_ARCHITECTURE.md` | Target architecture and service boundaries |
| `FRONTEND_CONTRACT.md` | What the dashboard may rely on from the API (states, polling, warnings) |
| `openapi.json` | Committed API snapshot; regenerate with `backend/scripts/dev/export_openapi.py` |
| `DATA_SOURCES.md` | Every evidence source, its grain, limits and status |
| `INTEGRATION_STATUS.md` | Branch map, verified cross-stack flow, remaining work |
| `TEST_STATUS.md` | Coverage and verified behaviour |
| `TEAM_EXECUTION.md` | Ownership split |
| `reports/` | Generated model and regional reports with figures (`backend/scripts/train/model_report.py`, `backend/scripts/data/analyze_regions.py`) |
| `product/` | Product architecture PDF |

Product and design intent live at the repository root: `../PRODUCT.md`, `../DESIGN.md`.
