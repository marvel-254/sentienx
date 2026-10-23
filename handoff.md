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

### Deployment (Render)
- Repo: https://github.com/marvel-254/sentienx
- Config: render.yaml (web service + Postgres)
- CI: .github/workflows/ci.yml (compile check + import smoke test)
- Build command: pip install -r requirements.txt
- Start command: streamlit run src/dashboard/unified_dashboard.py --server.port $PORT --server.headless true
- Env vars needed: DERIV_APP_ID, DERIV_API_TOKEN, FLASK_SECRET_KEY, DATABASE_URL (auto from render.yaml)
- Render API key stored in .render_env (gitignored)
- Deploy via Render dashboard (connect repo) or `render deploy` CLI

- Pi (claude-opus-4.7 via 9router) is available for delegation: `pi -p --provider 9router --model claude-opus-4.7 "task"`
- Terryan (this agent) handles orchestration, verification, and user communication
