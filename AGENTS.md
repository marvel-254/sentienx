# AGENTS.md — Sentienx Project Guide

## Project Identity
- **Name:** Sentienx
- **Type:** Trading dashboard (Streamlit + Flask + Deriv WebSocket)
- **Owner:** Langat Gideon (OmixSystems)
- **Location:** `/home/marvel/Downloads/sentienx`
- **Status:** Deployed on Render (Streamlit dashboard live; validate API server separately)

## Stack
- **UI:** Streamlit (Python), 13 tabs, dark theme
- **API:** Flask on port 8080
- **Data:** SQLite (`src/sentienx_trading.db`) locally, **PostgreSQL via `DATABASE_URL`** (Render/Neon) in deployment
- **Broker:** Deriv WebSocket (`wss://ws.derivws.com/websockets/v3`)
- **Charts:** Streamlit native + altair (plotly optional, matplotlib not installed)
- **ML:** Custom neural network, breakout analyzer in `src/ml/`
- **Risk:** VaR engine, portfolio allocator, stress tester in `src/risk_specialist/`

## Database
- Canonical adapter: `src/core/db_adapter.py` (`get_adapter()` singleton)
- Resolution: `DATABASE_URL` env → Postgres; else `SENTIENX_DB_PATH` or `src/sentienx_trading.db` (SQLite)
- On Render, `render.yaml` injects `DATABASE_URL` from a free Postgres instance; local dev stays SQLite
- Core tables: `trading_history`, `signals_history`; OpenStock tables: `watchlist`, `price_alerts`, `alert_events`
- SQLite `?` placeholders are auto-translated to `%s` for psycopg2; don't put literal `?` in queries
- Data transfer & verification: `scripts/migrate_sqlite_to_postgres.py`, `scripts/test_postgres_migration.py`

## Deployment
- **Live URL: https://sentienx-dashboard.onrender.com** (login: `SENTIENX_USER`/`SENTIENX_PASS` env, defaults marvel/olivertwist)
- Web service `sentienx-dashboard` `srv-dbdjdfjncjis73adijvg` (free) + Postgres `sentienx-db` `dpg-dbdj076q1p3s738pn42g-a` (free, oregon)
- Free Postgres expires after 30 days — check date before relying on it
- `autoDeploy` is ON: pushing to `master` re-deploys (~1–2 min)
- Deploy status: `GET /v1/services/srv-dbdjdfjncjis73adijvg/deploys` with Bearer `$RENDER_API_KEY` (stored in `.render_env`, untracked)
- Logs: `GET /v1/logs?ownerId=tea-d8t17777f7vs73blnoh0&resource=<svc-id>&limit=N&direction=forward`
- API gotchas: private-repo services CANNOT be created via `POST /v1/services`; `autoDeploy` must be string `"yes"`; build/start commands go inside `serviceDetails.envSpecificDetails`
- **GitHub repo `marvel-254/sentienx` is PUBLIC (user decision 2026-10-23)** — history is scrubbed of secrets; keep it clean, never commit tokens, keep `.env`/`.render_env` untracked
- Do NOT "Apply render.yaml" on Render — resources were provisioned via API; blueprint sync would duplicate the database
- Git history was rewritten (secrets scrubbed) on 2026-10-23 — old clones are stale

## Conventions
- Canonical code is in `src/` — top-level duplicates are legacy, do not edit them
- Python 3.14, venv at `.venv/`
- All imports use try/except guards — prefer making failures loud
- `.env` contains config; never commit real tokens
- DERIV_ENV should be "demo" during development

## Running
```bash
# Dashboard
.venv/bin/streamlit run src/dashboard/unified_dashboard.py --server.port 8501 --server.headless true

# API Server
.venv/bin/python src/api_server.py

# Compile check
.venv/bin/python -m py_compile src/dashboard/unified_dashboard.py
```

## Agent Coordination
- **Terryan** (this agent): orchestration, verification, user communication
- **Pi** (`pi -p --provider 9router --model claude-opus-4.7`): code tasks, refactoring, bulk edits
- Delegate large mechanical tasks to Pi; keep judgment calls (layout, architecture) here

## Key Risks
- Live trading mode (`DERIV_ENV=real`) with placeholder token — switch to demo
- No tests for trading logic
- Silent import failures mask broken features
- Dual codebase (src/ vs root) causes confusion
- Free Postgres instance expires (30 days) — deployed data is lost unless migrated

## What NOT to Do
- Do not edit top-level duplicate files (use src/ only)
- Do not enable real trading mode without valid token
- Do not install plotly (cached wheels are corrupted; use Streamlit native charts)
- Do not store real API tokens in .env commits
