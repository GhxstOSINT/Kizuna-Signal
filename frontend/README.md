# Frontend

React 18 + TypeScript + Vite dashboard. It only talks to the backend's `/api/v1` contract
(`../docs/openapi.json`) and shows an explicit recovery state when the API is down.

```bash
npm ci
npm run dev       # http://127.0.0.1:4173, proxies /api to http://127.0.0.1:8000
npm run build     # type-check (tsc -b) and production build
```

`VITE_API_URL` overrides the API base (default `/api/v1`). In Docker, nginx serves the build and
proxies `/api/` to the `api` service (`nginx.conf`, `Dockerfile`; build context is the repo root).

```
src/
  main.tsx          entry: fonts, router, styles
  App.tsx           routes and the API connection probe
  api/index.ts      fetch client, the `api` object, loadPortfolio
  api/types.ts      response types mirroring the backend schemas
  lib/seo.ts        title/description/keyword suggestions for the intake form
  components/       AppShell (frame, header, signal rail), Primitives (badges, states, fields)
  pages/            Portfolio, NewAnalysis, Analysis, Scenario, Playbook, Methodology
  styles/           base, shell, controls, portfolio, intake, analysis, scenario, playbook,
                    methodology, responsive, mobile-polish; index.css imports them in cascade order
```

Design intent is in `../PRODUCT.md`, `../DESIGN.md` and `../.impeccable/`.
