# AGENTS.md — Sentienx Project Guide

## Project Identity
- **Name:** Sentienx
- **Type:** Trading dashboard (Streamlit + Flask + Deriv WebSocket)
- **Owner:** Langat Gideon (OmixSystems)
- **Location:** `/home/marvel/Downloads/sentienx`
- **Status:** Half-finished prototype being revived

## Stack
- **UI:** Streamlit (Python), 9 tabs, dark theme
- **API:** Flask on port 8080
- **Data:** SQLite (`sentienx_trading.db`)
- **Broker:** Deriv WebSocket (`wss://ws.derivws.com/websockets/v3`)
- **Charts:** Streamlit native (plotly unavailable, matplotlib not installed)
- **ML:** Custom neural network, breakout analyzer in `src/ml/`
- **Risk:** VaR engine, portfolio allocator, stress tester in `src/risk_specialist/`

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
- No git history

## What NOT to Do
- Do not edit top-level duplicate files (use src/ only)
- Do not enable real trading mode without valid token
- Do not install plotly (cached wheels are corrupted; use Streamlit native charts)
- Do not store real API tokens in .env commits
