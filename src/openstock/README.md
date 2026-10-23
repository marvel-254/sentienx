# openstock - OpenStock-derived features for SENTIENX

Additive package porting OpenStock's dashboard and analytics concepts
into SENTIENX. Full plan: ../OPENSTOCK_MERGE_PLAN.md

## Modules

- quotes.py      unified Quote model + Finnhub (stocks) and Deriv adapters
- watchlist.py   SQLite-backed watchlist (single user)
- alerts.py      price alerts: rules, evaluation sweep, notifiers
- market_clock.py exchange session clock (NYSE, NASDAQ, LSE, JPX, DERIV)
- migrations.py  additive tables: watchlist, price_alerts, alert_events
- heatmap.py     Plotly treemap heatmap for Streamlit (lazy import)
- palette.py     command-palette action registry + Streamlit search box
- tradingview.py TradingView widget embeds for Streamlit (lazy import)
- tests/         stdlib unittest suite (pytest-compatible)

## Running tests

Core is stdlib-only; any Python >= 3.10 works:

    python3 -m unittest discover -s openstock/tests -v

## Integration (Phase 3)

Nothing here edits unified_dashboard.py. The dashboard owner mounts:

    from openstock import WatchlistRepository, AlertRepository, ActionRegistry
    from openstock import streamlit_pages  # Phase 3

## License

Ports derive from OpenStock, (c) Open Dev Society, licensed AGPL-3.0.
This package is therefore AGPL-3.0. Private personal use triggers no
obligations. If SENTIENX is distributed or served publicly, publish the
corresponding source under AGPL-3.0 and keep this notice.
