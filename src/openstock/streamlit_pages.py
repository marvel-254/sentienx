"""Streamlit pages for the OpenStock-derived market features.

Mounted by src/dashboard/unified_dashboard.py:
  * sidebar -> render_sidebar_palette()
  * tabs    -> render_watchlist_tab(), render_alerts_tab(),
               render_heatmap_tab(), render_symbol_detail_tab()

Design rules:
  * NEVER calls st.set_page_config (the host dashboard owns it)
  * session-state keys are prefixed ``ox_`` to avoid collisions
  * works with zero API keys: falls back to DemoProvider (clearly labeled);
    live Finnhub quotes activate automatically once FINNHUB_API_KEY is set
  * uses the same SQLite DB as the dashboard (src/sentienx_trading.db);
    tables are additive (CREATE TABLE IF NOT EXISTS) via migrations.py
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Tuple

from .alerts import AlertRepository
from .demo import DEFAULT_SYMBOLS, DERIV_SYMBOLS, DemoProvider
from .migrations import ensure_tables
from .notifiers import make_notifier
from .quotes import FinnhubProvider, Quote
from .watchlist import WatchlistRepository
from . import heatmap as heatmap_mod
from . import market_clock
from . import tradingview

# None -> repositories use the central core.db_adapter (SQLite locally,
# PostgreSQL when DATABASE_URL is set). Tests pass explicit paths.

# TradingView wants "EXCHANGE:SYMBOL"; most liquid US tickers are NASDAQ.
_TV_EXCHANGE_OVERRIDES = {
    "BABA": "NYSE", "DIS": "NYSE", "F": "NYSE", "GM": "NYSE", "JPM": "NYSE",
    "KO": "NYSE", "T": "NYSE", "WMT": "NYSE", "XOM": "NYSE",
}

_PROVIDER_CACHE: dict = {}


# ---------------------------------------------------------------------------
# providers / data helpers
# ---------------------------------------------------------------------------

def _env_file_key() -> str:
    """Read FINNHUB_API_KEY from the repo .env (no python-dotenv dep)."""
    env_file = Path(__file__).resolve().parents[2] / ".env"
    try:
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("FINNHUB_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


def resolve_provider() -> Tuple[object, str]:
    """Finnhub when a key exists (env or repo .env), else DemoProvider."""
    if "provider" in _PROVIDER_CACHE:
        return _PROVIDER_CACHE["provider"], _PROVIDER_CACHE["label"]
    key = os.environ.get("FINNHUB_API_KEY", "").strip() or _env_file_key()
    provider = None
    label = "demo"
    if key:
        try:
            provider = FinnhubProvider(key)
            label = "finnhub"
        except Exception:
            provider = None
    if provider is None:
        provider = DemoProvider()
    _PROVIDER_CACHE.update(provider=provider, label=label)
    return provider, label


def _market_for(symbol: str) -> str:
    return "deriv" if symbol.strip().upper() in DERIV_SYMBOLS else "stock"


def _safe_quote(provider, symbol: str) -> Optional[Quote]:
    try:
        return provider.get_quote(symbol)
    except Exception:
        return None


def _freshness_caption(quote: Optional[Quote], label: str) -> str:
    if quote is None:
        return f"⚠️ no quote · provider: {label}"
    if label == "demo":
        return "🟡 demo data — set FINNHUB_API_KEY in .env for live quotes"
    ts = (quote.timestamp or "")[:19].replace("T", " ") + " UTC"
    state = "🟢 live" if not quote.stale else "🟡 stale"
    return f"{state} · {ts} · {quote.source}"


# ---------------------------------------------------------------------------
# symbol universe (pure helpers are unit-tested)
# ---------------------------------------------------------------------------

def symbol_universe(db_path=None, cap: int = 40) -> List[Tuple[str, str]]:
    """Watchlist entries first, then defaults; deduped by symbol."""
    seen: set = set()
    out: List[Tuple[str, str]] = []
    try:
        for row in WatchlistRepository(db_path).list():
            if row["symbol"] not in seen:
                seen.add(row["symbol"])
                out.append((row["symbol"], row["market"]))
    except Exception:
        pass
    for sym, mkt in DEFAULT_SYMBOLS:
        if sym not in seen and len(out) < cap:
            seen.add(sym)
            out.append((sym, mkt))
    return out


def filter_universe(
    universe: List[Tuple[str, str]], query: str, limit: int = 8
) -> List[Tuple[str, str]]:
    """Prefix matches first, then substring. Pure function."""
    q = (query or "").strip().upper()
    if not q:
        return universe[:limit]
    starts = [p for p in universe if p[0].startswith(q)]
    contains = [p for p in universe if q in p[0] and not p[0].startswith(q)]
    return (starts + contains)[:limit]


# ---------------------------------------------------------------------------
# rendering helpers
# ---------------------------------------------------------------------------

def _show_table(records: List[dict]):
    """st.dataframe when pyarrow exists, dependency-free HTML table otherwise."""
    import streamlit as st

    if not records:
        return
    try:
        import pandas as pd

        st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)
    except Exception:
        cols = list(records[0].keys())
        head = "".join(
            f'<th style="text-align:left;padding:4px 10px;'
            f'border-bottom:1px solid #30363d">{c}</th>' for c in cols
        )
        body = "".join(
            "<tr>"
            + "".join(
                f'<td style="padding:4px 10px">{"" if row.get(c) is None else row.get(c)}</td>'
                for c in cols
            )
            + "</tr>"
            for row in records
        )
        st.markdown(
            '<div style="overflow-x:auto"><table style="width:100%;'
            f'border-collapse:collapse;font-size:0.9rem"><thead><tr>{head}</tr>'
            f"</thead><tbody>{body}</tbody></table></div>",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# sidebar
# ---------------------------------------------------------------------------

def render_sidebar_palette():
    """Command-palette-style symbol search + quick actions (sidebar)."""
    import streamlit as st

    ensure_tables()
    provider, label = resolve_provider()
    st.markdown("**🔎 Market Palette**")

    universe = symbol_universe()
    query = st.text_input(
        "Symbol search", "", key="ox_palette_query",
        placeholder="AAPL, NVDA, R_100 …",
    )
    matches = filter_universe(universe, query)
    if matches:
        labels = [f"{s} · {m}" for s, m in matches]
        choice = st.selectbox(
            "Matches", labels, key="ox_palette_pick", label_visibility="collapsed"
        )
        symbol = choice.split("·")[0].strip()
        st.session_state["ox_symbol"] = symbol
        col_a, col_b = st.columns(2)
        if col_a.button("＋ Watch", key="ox_palette_watch", use_container_width=True):
            added = WatchlistRepository().add(symbol, _market_for(symbol))
            st.toast(f"{symbol} {'added to' if added else 'already in'} watchlist")
        if col_b.button("🔔 Alert", key="ox_palette_alert", use_container_width=True):
            st.session_state["ox_alert_symbol"] = symbol
            st.toast(f"Create the alert for {symbol} in the Price Alerts tab")
    else:
        st.caption("No match — try a ticker like AAPL")
    st.caption(f"data: {label}")


# ---------------------------------------------------------------------------
# tabs
# ---------------------------------------------------------------------------

def render_watchlist_tab():
    import streamlit as st

    ensure_tables()
    provider, label = resolve_provider()
    repo = WatchlistRepository()

    st.subheader("📋 Watchlist")
    st.caption(
        market_clock.market_status_line("NYSE")
        + " · " + market_clock.market_status_line("NASDAQ")
        + " · " + market_clock.market_status_line("DERIV")
    )

    with st.form("ox_watchlist_add", clear_on_submit=True):
        c1, c2, c3 = st.columns([3, 2, 1])
        symbol = c1.text_input(
            "Symbol", placeholder="AAPL or R_100", key="ox_watch_sym"
        ).strip().upper()
        market = c2.selectbox("Market", ("stock", "deriv"), key="ox_watch_market")
        submitted = c3.form_submit_button("Add", use_container_width=True)
    if submitted and symbol:
        if repo.add(symbol, market):
            st.toast(f"{symbol} added to watchlist")
        else:
            st.toast(f"{symbol} is already on the watchlist")

    rows = repo.list()
    if not rows:
        st.info("Watchlist is empty — add a symbol above or from the sidebar palette.")
        return

    records = []
    for row in rows:
        q = _safe_quote(provider, row["symbol"])
        records.append({
            "Symbol": row["symbol"],
            "Market": row["market"],
            "Price": None if q is None or q.price is None else round(q.price, 4),
            "Change %": (
                None if q is None or q.change_percent is None
                else round(q.change_percent, 2)
            ),
            "Source": "—" if q is None else q.source,
            "Added": (row.get("added_at") or "")[:16],
        })
    _show_table(records)
    st.caption(_freshness_caption(None, label).split("·")[-1].strip())

    with st.form("ox_watchlist_remove"):
        victims = st.multiselect(
            "Remove symbols", [r["symbol"] for r in rows], key="ox_watch_rm"
        )
        if st.form_submit_button("Remove selected"):
            for v in victims:
                repo.remove(v)
            if victims:
                st.rerun()


def render_alerts_tab():
    import streamlit as st

    ensure_tables()
    provider, label = resolve_provider()
    repo = AlertRepository(notifier=make_notifier())

    st.subheader("🔔 Price Alerts")
    st.caption(
        f"data: {label} · alerts are checked when you press **Check now** "
        "(automatic background sweep lands in Phase 2)"
    )

    preset = st.session_state.get("ox_alert_symbol", "")
    with st.form("ox_alert_create", clear_on_submit=True):
        c1, c2, c3 = st.columns([2, 1, 1])
        symbol = c1.text_input(
            "Symbol", value=preset, key=f"ox_alert_sym_{preset}"
        ).strip().upper()
        condition = c2.selectbox("Condition", ("above", "below"), key="ox_alert_cond")
        preset_target = float(st.session_state.get("ox_alert_target") or 0.0)
        target = c3.number_input(
            "Target price", min_value=0.0, step=0.01,
            value=preset_target, key=f"ox_alert_target_{preset}",
        )
        note = st.text_input("Note (optional)", key="ox_alert_note")
        submitted = st.form_submit_button("Create alert", use_container_width=True)
    if submitted:
        if not symbol or target <= 0:
            st.warning("Enter a symbol and a target price above 0.")
        else:
            alert = repo.create(
                symbol, condition, float(target),
                market=_market_for(symbol), note=note or None,
            )
            st.success(f"Alert #{alert.id} created: {symbol} {condition} {target:g}")

    all_alerts = repo.list()
    if all_alerts:
        st.markdown("**Alerts**")
        _show_table([{
            "ID": a.id,
            "Symbol": a.symbol,
            "Condition": a.condition,
            "Target": a.target_price,
            "Status": a.status,
            "Last seen": a.last_checked_price,
            "Created": (a.created_at or "")[:16],
        } for a in all_alerts])
        with st.form("ox_alert_manage"):
            pick = st.selectbox(
                "Manage alert",
                [f"#{a.id} {a.symbol} {a.condition} {a.target_price:g} ({a.status})"
                 for a in all_alerts],
                key="ox_alert_manage_pick",
            )
            c1, c2, c3 = st.columns(3)
            pause = c1.form_submit_button("⏸ Pause", use_container_width=True)
            resume = c2.form_submit_button("▶ Resume", use_container_width=True)
            delete = c3.form_submit_button("🗑 Delete", use_container_width=True)
            alert_id = int(pick.split()[0].lstrip("#"))
            if pause:
                repo.set_status(alert_id, "paused")
                st.rerun()
            if resume:
                repo.set_status(alert_id, "active")
                st.rerun()
            if delete:
                repo.delete(alert_id)
                st.rerun()
    else:
        st.info("No alerts yet — create one above.")

    if st.button("🔄 Check now", key="ox_alert_check"):
        with st.spinner("Evaluating alerts…"):
            fired = repo.evaluate(provider)
        hits = [f for f in fired if "error" not in f]
        errors = [f for f in fired if "error" in f]
        if hits:
            for f in hits:
                st.toast(f"🚨 {f['symbol']} {f['condition']} {f.get('price')}")
            st.success(f"{len(hits)} alert(s) fired — see events below.")
        elif errors:
            st.warning(f"{len(errors)} symbol(s) could not be checked.")
        else:
            st.info("No alerts fired.")

    events = repo.list_events(limit=15)
    st.markdown("**Recent events**")
    if events:
        _show_table([{
            "When": (e.get("fired_at") or "")[:19],
            "Symbol": e.get("symbol"),
            "Condition": e.get("condition"),
            "Price": e.get("price"),
            "Target": e.get("target_price"),
            "Via": e.get("delivered_via"),
        } for e in events])
    else:
        st.caption("No alert events yet.")


def render_heatmap_tab():
    import streamlit as st

    ensure_tables()
    provider, label = resolve_provider()
    st.subheader("🔥 Market Heatmap")

    universe = symbol_universe()[:24]  # Finnhub free tier: 60 req/min
    quotes = [q for q in (_safe_quote(provider, s) for s, _ in universe)
              if q is not None]
    rows = heatmap_mod.build_heatmap_rows(quotes)
    if not rows:
        st.info("No quote data available for the heatmap.")
        return
    heatmap_mod.render_streamlit(rows)  # plotly if present, else HTML grid
    st.caption(f"data: {label} · tiles colored by % change (green up, red down)")


def render_symbol_detail_tab():
    import streamlit as st

    ensure_tables()
    provider, label = resolve_provider()
    st.subheader("📈 Symbol Detail")

    universe = symbol_universe()
    symbols = [s for s, _ in universe]
    preferred = st.session_state.get("ox_symbol")
    if preferred and preferred not in symbols:
        symbols.insert(0, preferred)
    if not symbols:
        st.info("No symbols available.")
        return
    idx = symbols.index(preferred) if preferred in symbols else 0
    symbol = st.selectbox("Symbol", symbols, index=idx, key="ox_detail_pick")
    st.session_state["ox_symbol"] = symbol

    market = _market_for(symbol)
    quote = _safe_quote(provider, symbol)

    c1, c2, c3, c4 = st.columns(4)
    price = quote.price if quote and quote.price is not None else None
    c1.metric(
        "Price",
        f"{price:g}" if price is not None else "—",
        delta=(
            f"{quote.change_percent:+.2f}%"
            if quote and quote.change_percent is not None else None
        ),
    )
    c2.metric(
        "Day range",
        f"{quote.low:g} – {quote.high:g}"
        if quote and quote.low and quote.high else "—",
    )
    c3.metric("Open", f"{quote.open:g}" if quote and quote.open else "—")
    c4.metric(
        "Prev close",
        f"{quote.previous_close:g}" if quote and quote.previous_close else "—",
    )
    session_code = "NYSE" if market == "stock" else "DERIV"
    st.caption(
        _freshness_caption(quote, label)
        + " · " + market_clock.market_status_line(session_code)
    )

    if market == "stock":
        tv_symbol = f"{_TV_EXCHANGE_OVERRIDES.get(symbol, 'NASDAQ')}:{symbol}"
        chart_tab, tech_tab = st.tabs(["Chart", "Technicals"])
        with chart_tab:
            tradingview.render_streamlit(tv_symbol, "advanced-chart", height=460)
        with tech_tab:
            tradingview.render_streamlit(tv_symbol, "technical-analysis", height=460)
    else:
        st.info(
            "TradingView doesn't cover Deriv synthetics — live tick charts "
            "arrive with the Phase 2 Deriv wiring."
        )

    c1, c2 = st.columns(2)
    if c1.button("＋ Add to watchlist", key="ox_detail_watch", use_container_width=True):
        added = WatchlistRepository().add(symbol, market)
        st.toast(f"{symbol} {'added to' if added else 'already in'} watchlist")
    if c2.button("🔔 Alert at this price", key="ox_detail_alert", use_container_width=True):
        st.session_state["ox_alert_symbol"] = symbol
        if price is not None:
            st.session_state["ox_alert_target"] = float(price)
        st.toast(f"Price Alerts tab: create the alert for {symbol}")
