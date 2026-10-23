#!/usr/bin/env python3
"""Postgres end-to-end verification for the SQLite->Postgres migration.

Run with DATABASE_URL pointing at a test Postgres instance.
"""
import os
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://sxtest:sxtest@localhost:55432/sxtest",
)

failures = []


def check(name, fn):
    try:
        fn()
        print(f"PASS  {name}")
    except Exception as e:
        failures.append((name, e))
        print(f"FAIL  {name}: {e!r}")


from core.db_adapter import DatabaseAdapter  # after env set

adapter = DatabaseAdapter()


def t_is_postgres():
    assert adapter.is_postgres, "adapter should be in postgres mode"


def t_schema():
    tables = adapter.ensure_schema()
    for t in ("trading_history", "signals_history"):
        assert t in tables, f"{t} missing: {tables}"


def t_reset_trades():
    adapter.execute("DELETE FROM trading_history")
    adapter.execute("DELETE FROM signals_history")


def t_insert_and_hooks():
    for row in [
        ("EUR/USD", "BUY", 1.0850, 1.0920, 10.0, 70.0, "closed", "2026-10-20 10:00:00", "breakout"),
        ("GBP/USD", "BUY", 1.2650, 1.2600, 5.0, -25.0, "closed", "2026-10-20 11:00:00", "breakout"),
        ("EUR/USD", "SELL", 1.0930, 1.0880, 20.0, 100.0, "closed", "2026-10-21 09:30:00", "momentum"),
        ("USD/JPY", "BUY", 150.25, 0.0, 8.0, 0.0, "open", "2026-10-21 14:00:00", "manual"),
    ]:
        adapter.execute(
            "INSERT INTO trading_history (symbol, direction, entry_price, exit_price, "
            "volume, profit_loss, status, timestamp, strategy) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            row,
        )
    n = adapter.fetchone("SELECT COUNT(*) as c FROM trading_history")["c"]
    assert n == 4, f"expected 4 rows, got {n}"


def t_date_cast():
    row = adapter.fetchone("""
        SELECT (timestamp)::date as date, SUM(profit_loss) as daily_pnl
        FROM trading_history GROUP BY (timestamp)::date ORDER BY date
    """) if adapter.is_postgres else adapter.fetchone(
        "SELECT DATE(timestamp) as date FROM trading_history LIMIT 1"
    )


def t_pnl_sql_like_dashboard():
    d = adapter.date_expr("timestamp")
    df = adapter.read_df(f"""
        SELECT {d} as date, SUM(profit_loss) as daily_pnl, COUNT(*) as trades,
               SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as wins
        FROM trading_history GROUP BY {d} ORDER BY date ASC
    """)
    assert list(df["daily_pnl"]) == [45.0, 100.0] or list(df["cumulative_pnl"]) == [45.0, 100.0], df
    assert df["date"].iloc[0] <= df["date"].iloc[1]


def t_dashboard_loaders():
    from dashboard import unified_dashboard as ud  # noqa: E402

    trades = ud.load_trades_data(10)
    assert len(trades) == 4, trades
    pnl = ud.load_pnl_data()
    assert not pnl.empty and list(pnl["cumulative_pnl"])[-1] == 145.0, pnl
    sig = ud.load_signals_data(5)
    assert sig.empty, "signals table should be empty"
    acct = ud.load_account_data()
    assert acct["total_trades"] == 4, acct
    assert abs(acct["total_pnl"] - 145.0) < 1e-6, acct
    assert acct["open_positions"] == 1, acct
    assert acct["win_rate"] == 50.0, acct  # 2 wins of 4 trades
    assert acct["profit_factor"] > 0, acct


def t_openstock_crud():
    from openstock.watchlist import WatchlistRepository
    from openstock.alerts import AlertRepository
    from openstock.migrations import ensure_tables

    ensure_tables()
    wl = WatchlistRepository()
    assert wl.add("AAPL"), "first add should succeed"
    assert not wl.add("AAPL"), "duplicate add should be ignored"
    assert wl.has("AAPL")
    rows = wl.list()
    assert rows[0]["symbol"] == "AAPL" and isinstance(rows[0]["added_at"], str), rows
    assert wl.remove("AAPL")

    al = AlertRepository()
    alert = al.create("TSLA", "above", 250.5, note="e2e")
    assert alert.id, alert
    got = al.get(alert.id)
    assert got.symbol == "TSLA" and got.created_at, got
    assert al.set_status(alert.id, "paused")
    assert al.get(alert.id).status == "paused"
    assert al.delete(alert.id)
    assert al.list() == []


def t_api_server():
    from api.server import app  # noqa: E402

    client = app.test_client()
    r = client.get("/api/health")
    assert r.status_code == 200 and r.get_json()["status"] == "healthy", r.get_json()
    r = client.get("/api/account")
    j = r.get_json()
    assert r.status_code == 200 and j["total_trades"] == 4 and abs(j["total_pnl"] - 145.0) < 1e-6, j
    r = client.get("/api/trades?limit=2")
    j = r.get_json()
    assert r.status_code == 200 and j["count"] == 2, j
    r = client.get("/api/statistics")
    j = r.get_json()
    assert j["win_rate"] == 50.0, j
    r = client.get("/api/pnl")
    j = r.get_json()
    assert r.status_code == 200 and j["count"] == 2 and abs(j["pnl_data"][1]["cumulative_pnl"] - 145.0) < 1e-6, j
    r = client.get("/api/pnl/breakdown")
    j = r.get_json()
    assert abs(j["profitable_trades"] - 170.0) < 1e-6 and abs(j["losing_trades"] - 25.0) < 1e-6, j
    r = client.get("/api/bot/strength")
    j = r.get_json()
    assert 0 <= j["strength"] <= 100, j


def insert_signals():
    adapter.execute(
        "INSERT INTO signals_history (symbol, signal, confidence, strength, indicators, timestamp, strategy) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("EUR/USD", "1", 0.82, 0.9, "RSI", "2026-10-22 09:00:00", "ml"),
    )


def t_signals_loader():
    from dashboard import unified_dashboard as ud  # noqa: E402

    sig = ud.load_signals_data(5)
    assert len(sig) == 1 and sig.iloc[0]["symbol"] == "EUR/USD", sig


if __name__ == "__main__":
    check("adapter->postgres", t_is_postgres)
    check("core schema", t_schema)
    check("seed trades", t_reset_trades)
    check("insert ?-params", t_insert_and_hooks)
    check("date cast", t_date_cast)
    check("pnl sql", t_pnl_sql_like_dashboard)
    check("dashboard loaders", t_dashboard_loaders)
    check("openstock crud", t_openstock_crud)
    check("api server routes", t_api_server)
    check("signals loader", insert_signals)
    check("signals loader", t_signals_loader)

    print()
    if failures:
        print(f"{len(failures)} FAILURE(S)")
        sys.exit(1)
    print("ALL POSTGRES TESTS PASSED")
