# SENTIENX x OpenStock Merge Plan

Status: DRAFT v1 (foundation laid)
Date: 2026-10-13
Owners: Langat Gideon (sir) + Agora agent
Constraint: other agents are actively working in this folder. All changes
from this plan are ADDITIVE ONLY (new files, new tables). No existing file
is modified by this plan unless sir explicitly approves it.

## 1. Objective

Port OpenStock's dashboard and analytics experience into SENTIENX so the
trading system gains a proper market-viewing layer: watchlist, price
alerts, market heatmap, command palette, symbol detail views, and market
status. SENTIENX keeps everything OpenStock does not have: the trading
bot, ML pipeline, backtesting, and risk engine.

## 2. Decisions locked by sir (2026-10-13)

1. Reuse OpenStock code (AGPL-3.0 accepted), not just ideas.
2. Frontend stays Streamlit. No Next.js.
3. Personal use, single user.
4. Markets: BOTH Deriv and stocks (Finnhub).
5. Feature scope: everything, priority order: command palette, alerts,
   heatmap, watchlist, then the rest.
6. Project stays at ~/Downloads/sentienx. Do not move it.

## 3. License compliance (AGPL-3.0)

OpenStock is (c) Open Dev Society, AGPL-3.0. Because we reuse its code:

- SENTIENX becomes a derivative work of OpenStock. The openstock package
  and any distributed or network-served version of SENTIENX must ship
  under AGPL-3.0 with attribution to Open Dev Society.
- Private personal use on this machine triggers NO obligations.
- If SENTIENX is ever deployed as a public web service or shared, the
  full corresponding source must be published under AGPL-3.0.
- Attribution lives in openstock/README.md. Keep it.

## 4. Source map (OpenStock file -> SENTIENX port)

| OpenStock (TypeScript/React)              | SENTIENX port (Python/Streamlit)        |
|-------------------------------------------|-----------------------------------------|
| lib/actions/finnhub.actions.ts            | openstock/quotes.py (FinnhubProvider)   |
| deriv_connector.py + ws_client.py (ours)  | openstock/quotes.py (DerivProvider)     |
| database/models/watchlist.model.ts        | openstock/watchlist.py + migrations.py  |
| lib/actions/watchlist.actions.ts          | openstock/watchlist.py                  |
| database/models/alert.model.ts            | openstock/alerts.py + migrations.py     |
| lib/actions/alert.actions.ts              | openstock/alerts.py (evaluate sweep)    |
| lib/inngest/functions.ts (alert cron)     | openstock/alerts.py called on a timer   |
| lib/market-session.ts + lib/markets.ts    | openstock/market_clock.py               |
| components/landing/MarketClock.tsx        | openstock/market_clock.py status line   |
| components/SearchCommand.tsx + cmdk       | openstock/palette.py (ActionRegistry)   |
| components/TradingViewWidget.tsx          | openstock/tradingview.py                |
| dashboard heatmap (TradingView)           | openstock/heatmap.py (Plotly treemap)   |
| components/ChangePill, PriceFlash,        | Streamlit metrics + custom CSS in       |
| IndexPulse, PulseTile, DataFreshness      | openstock/streamlit_pages.py (Phase 3)  |
| components/watchlist/* (table, alerts)    | openstock/streamlit_pages.py (Phase 3)  |
| app/(root)/stocks/[symbol]/page.tsx       | symbol detail page (Phase 3)            |
| components/stocks/StockSentimentCard.tsx  | sentiment card (Phase 4, optional)      |

## 5. Architecture

    unified_dashboard.py (existing, untouched by this plan)
        |
        |-- mounts --> openstock/streamlit_pages.py   (Phase 3)
        |                 |-- watchlist page
        |                 |-- alerts page
        |                 |-- heatmap page
        |                 |-- symbol detail page
        |                 |-- palette (sidebar search)
        |
        |-- imports -> openstock core (stdlib-only, testable)
                          |-- quotes.py      unified Quote + providers
                          |-- watchlist.py   SQLite CRUD
                          |-- alerts.py      rules + evaluation sweep
                          |-- market_clock.py session logic
                          |-- migrations.py   additive tables
                          |-- heatmap.py / palette.py / tradingview.py (UI helpers)

Design rules:
- Core modules import only the standard library so they run in ANY venv
  (all three current venvs are broken or partial).
- UI helpers import streamlit/plotly lazily, matching the existing
  HAS_PLOTLY pattern in unified_dashboard.py.
- One Quote interface, two markets: 'stock' (Finnhub REST) and 'deriv'
  (adapter over deriv_connector.py; tick streaming via ws_client.py in
  Phase 2).

## 6. Database changes (additive, idempotent)

Applied by openstock/migrations.py (CREATE TABLE IF NOT EXISTS):

- watchlist(id, symbol, market, display_name, added_at, note) UNIQUE(symbol, market)
- price_alerts(id, symbol, market, condition above|below, target_price,
  note, status active|paused|triggered|cancelled, created_at,
  triggered_at, last_checked_price)
- alert_events(id, alert_id FK, symbol, price, target_price, condition,
  fired_at, delivered_via)

Existing trading_history table is untouched.

## 7. Roadmap

Phase 0 - Environment repair (needs sir approval, may touch venvs)
  [ ] Rebuild ONE clean venv (suggest replacing the three with a single
      .venv) with streamlit, plotly, pandas, requests, pytest.
  [ ] Fix sentienx_env/bin/pip permission bits or retire it.
  Acceptance: `python -m pytest openstock/tests` green in the new venv.

Phase 1 - Foundation (DONE 2026-10-13, this plan + openstock package)
  [x] openstock/ package: quotes, watchlist, alerts, market_clock,
      heatmap, palette, tradingview, migrations
  [x] stdlib unittest suite in openstock/tests/
  [x] No existing files modified.

Phase 2 - Live data wiring
  [ ] FINNHUB_API_KEY into .env (sir creates free key at finnhub.io).
  [ ] DerivProvider tick quotes via ws_client.py (candles + ticks).
  [ ] Alert sweep on a background thread (60s interval) started from
      run.sh or process_manager.py (needs owner approval).
  [ ] Notification channel: pick ONE for v1 (see Open questions).

Phase 3 - Dashboard integration (owner of unified_dashboard.py applies)
  [ ] Sidebar: palette search box + market status line.
  [ ] Pages: Watchlist, Alerts, Heatmap, Symbol Detail.
  [ ] Symbol detail: TradingView advanced chart + technicals + profile,
      Add-to-watchlist button, Create-alert form.
  [ ] Heatmap page: treemap by market/sector from live quotes.

Phase 4 - Polish (per advanced-frontend skill)
  [ ] Dark theme tokens matched to existing #0a0e27 palette.
  [ ] Subtle 200-300ms transitions on state changes (CSS only).
  [ ] DataFreshness indicator (stale quotes flagged).
  [ ] Sentiment card (Reddit/X/news) if wanted.

## 8. Integration contract

This plan does NOT edit unified_dashboard.py. It provides:
- openstock/streamlit_pages.py (Phase 3) with render functions:
  render_watchlist_page(), render_alerts_page(), render_heatmap_page(),
  render_symbol_detail(symbol), render_palette(registry).
- Whoever owns the dashboard adds ONE import and ONE sidebar block.
- openstock core is importable today: `from openstock import ...`

## 9. Testing

- openstock/tests/test_core.py: stdlib unittest (also runs under pytest).
  Covers migrations idempotency, watchlist CRUD + dedup, alert rule
  logic, alert evaluation with a fake provider, market clock (weekend,
  session hours, Deriv always-on), palette search ranking.
- Run: python3 -m unittest discover -s openstock/tests -v
- Phase 2 adds network-level tests behind a skip-if-no-key guard.

## 10. Risks and constraints

- Three broken venvs: core is stdlib-only to stay runnable, but Phase 0
  should consolidate before Phase 3 UI work.
- Finnhub free tier: delayed quotes, 60 calls/min. Alert sweeps must
  batch and cache. Deriv synthetics are 24/7 so they sweep cheaply.
- Other agents may create files concurrently: this plan only claims the
  openstock/ namespace and OPENSTOCK_MERGE_PLAN.md.
- Streamlit has no native Cmd+K overlay; palette v1 is a search box.
  A custom component can upgrade it later without changing call sites.

## 11. Open questions for sir

1. Alert notifications: email (smtplib), Telegram bot, or desktop
   notification for v1?
2. Does sir already have a Finnhub API key, or should the plan assume a
   new free signup?
3. Who owns unified_dashboard.py integration (which agent), so Phase 3
   can be coordinated?
4. Approve Phase 0 venv consolidation?
