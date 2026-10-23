# Sentienx — Handoff Document

## Project Summary
Sentienx is a Streamlit-based trading dashboard for Deriv accounts. It includes live account balance, trade history, P&L charts, trading signals, economic calendar, market news, AI assistant tab, and a Flask REST API. Currently a half-finished prototype being revived.

## Current State (as of 2026-10-22)

### Environment
- Fresh `.venv` on Python 3.14 at `/home/marvel/Downloads/sentienx/.venv`
- Broken `sentienx_env` (old path) removed
- Installed: streamlit 1.66.1, flask 3.1.3, pandas 3.1.0, numpy 2.5.4, requests 2.34.2, sqlalchemy 2.1.6, websockets 17.3, protobuf, click, starlette, packaging, werkzeug, blinker, jinja2, itsdangerous, python-dateutil, uvicorn
- NOT installed: plotly (cached wheels corrupted), matplotlib (not attempted)
- HAS_PLOTLY = False — all chart functions gracefully fall back to Streamlit native charts (st.line_chart, st.bar_chart, st.metric)

### Code Layout
- Canonical code lives in `src/` (54 Python files)
- Duplicate top-level copies still exist (legacy) — consolidation pending
- `src/dashboard/unified_dashboard.py` compiles clean, imports pass
- `src/dashboard/app.py` exists as alternate entry point

### Key Files
- `src/dashboard/unified_dashboard.py` — main dashboard (9 tabs)
- `src/api/` — Flask API server (port 8080)
- `src/core/` — shared types, data processor
- `src/trading/` — connector, ws_client, advanced_signals
- `src/ml/` — neural network, breakout analyzer
- `src/risk_specialist/` — portfolio allocator, VaR, stress tester
- `.env` — config (placeholder Deriv token, DERIV_ENV=real — CHANGE TO DEMO)
- `sentienx_trading.db` — SQLite trade log (root level)

### Known Issues
1. Plotly not installed — charts use Streamlit native fallbacks
2. `.env` has placeholder token (`***`) and DERIV_ENV=real — switch to demo before running
3. Dual code layout: `src/` vs top-level duplicates not consolidated
4. Import guards (try/except) silently disable features — need to make failures loud
5. Microservice URLs in .env (ports 5000/5001/8002) — verify those services exist
6. `ml_pipeline/` has its own `sentienx_trading.db` — possible DB split-brain
7. No git history — can't track what worked vs abandoned
8. No tests beyond `dashboard/test_dashboard.py`

### Next Steps
1. Consolidate codebase: `src/` only, remove top-level duplicates
2. Switch `.env` to DERIV_ENV=demo, add valid demo token
3. Run dashboard locally: `.venv/bin/streamlit run src/dashboard/unified_dashboard.py --server.port 8501`
4. Verify each tab renders with real or mock data
5. Make import failures loud (remove silent try/except guards)
6. Add tests for trading logic, risk calc, signal generation
7. Install plotly or matplotlib when network available

### Running the Dashboard
```bash
cd /home/marvel/Downloads/sentienx
.venv/bin/streamlit run src/dashboard/unified_dashboard.py --server.port 8501 --server.headless true
```

### Running the API Server
```bash
cd /home/marvel/Downloads/sentienx
.venv/bin/python src/api_server.py  # or src/api/...
```

### Deployment (Render) — LIVE as of 2026-10-23
- **URL: https://sentienx-dashboard.onrender.com**
- Web service `sentienx-dashboard` (id `srv-dbdjdfjncjis73adijvg`, free plan, Python runtime)
- Postgres `sentienx-db` (id `dpg-dbdj076q1p3s738pn42g-a`, free plan, oregon)
  - ⚠️ Render free Postgres expires after 30 days — plan migration to a paid instance or new free DB before expiry
  - External (SSL) conn string for psql: `dpg-dbdj076q1p3s738pn42g-a.oregon-postgres.render.com:5432/sentienx`; internal form is `dpg-dbdj076q1p3s738pn42g-a/sentienx` (used in `DATABASE_URL`)
- `DATABASE_URL` env var on the service holds the INTERNAL connection string (fast path, no egress cost)
- autoDeploy: every push to `master` → auto re-deploy (~1–2 min). Watch: `GET /v1/services/srv-dbdjdfjncjis73adijvg/deploys`
- Deploy history + API gotchas (source: 2026-10-23 session):
  - Render API **cannot create** services from PRIVATE repos ("repository URL is invalid or unfetchable"); public repos work
  - Actual deployed flow was: scrub secrets from git history (git-filter-repo) → flip repo public → `POST /v1/services` → flip private immediately
  - `POST /v1/services` body gotchas: `autoDeploy` must be STRING `"yes"` (not bool); `buildCommand`/`startCommand` go inside `serviceDetails.envSpecificDetails = {buildCommand, startCommand}`; `serviceDetails: {env: "python", envSpecificDetails: {...}, plan: "free"}` required for non-static services
  - Create Postgres: `POST /v1/postgres {name, ownerId, plan, version, databaseName, databaseUser}` (older attempts failed on missing `ownerId` and `version`)
  - Logs (new-style endpoint): `GET /v1/logs?ownerId=<team-id>&resource=<svc-id>&limit=N&direction=forward` — NOT `/v1/services/…/logs`
- Auth on the dashboard: `SENTIENX_USER`/`SENTIENX_PASS` env vars, defaults marvel/olivertwist if unset (service currently uses defaults)
- Env vars: DERIV_ENV=demo, DERIV_APP_ID, DERIV_API_TOKEN, FLASK_SECRET_KEY, PYTHON_VERSION=3.14.0, DATABASE_URL
- SECURITY: `.render_env` contained a live Render API key committed to old git history — key was scrubbed in rewrite (commit b67b7a9f) but **rotate it anyway**; rotate the Deriv token too
- Do NOT "Apply render.yaml" on Render for this repo: resources already provisioned via API; a blueprint sync would try to create a second database
- Repo master was history-rewritten (force-push): old clones are stale, re-clone before pushing
- Seed/transfer data: `DATABASE_URL=... python scripts/migrate_sqlite_to_postgres.py`
- Verify migration: `DATABASE_URL=... python scripts/test_postgres_migration.py` (must run from a network that can reach the DB — local box egress to Render Postgres was blocked during testing; drives from the deployed app or Render's network instead)

- Pi (claude-opus-4.7 via 9router) is available for delegation: `pi -p --provider 9router --model claude-opus-4.7 "task"`
- Terryan (this agent) handles orchestration, verification, and user communication
