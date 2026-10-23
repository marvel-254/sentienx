"""Additive migrations for OpenStock-derived features.

Creates the tables needed by the openstock package (watchlist,
price_alerts, alert_events) in whichever database the central
adapter resolves (SQLite locally, PostgreSQL when DATABASE_URL is
set). Every statement is CREATE TABLE IF NOT EXISTS, so running this
is idempotent. The core trading_history / signals_history tables are
never touched.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union

try:
    from core.db_adapter import get_adapter
except ImportError:  # openstock imported without src/ on sys.path
    from .db_adapter import get_adapter  # shim bootstraps src/ and re-exports

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "sentienx_trading.db"

_SCHEMA = {
    "sqlite": [
        """
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            market TEXT NOT NULL DEFAULT 'stock',
            display_name TEXT,
            added_at TEXT NOT NULL DEFAULT (datetime('now')),
            note TEXT,
            UNIQUE(symbol, market)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS price_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            market TEXT NOT NULL DEFAULT 'stock',
            condition TEXT NOT NULL CHECK (condition IN ('above', 'below')),
            target_price REAL NOT NULL,
            note TEXT,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'paused', 'triggered', 'cancelled')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            triggered_at TEXT,
            last_checked_price REAL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS alert_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id INTEGER NOT NULL REFERENCES price_alerts(id),
            symbol TEXT NOT NULL,
            price REAL NOT NULL,
            target_price REAL NOT NULL,
            condition TEXT NOT NULL,
            fired_at TEXT NOT NULL DEFAULT (datetime('now')),
            delivered_via TEXT NOT NULL DEFAULT 'log'
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_price_alerts_active ON price_alerts(status, symbol)",
        "CREATE INDEX IF NOT EXISTS idx_alert_events_alert ON alert_events(alert_id)",
    ],
    "postgres": [
        """
        CREATE TABLE IF NOT EXISTS watchlist (
            id BIGSERIAL PRIMARY KEY,
            symbol TEXT NOT NULL,
            market TEXT NOT NULL DEFAULT 'stock',
            display_name TEXT,
            added_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'utc', 'YYYY-MM-DD HH24:MI:SS'),
            note TEXT,
            UNIQUE(symbol, market)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS price_alerts (
            id BIGSERIAL PRIMARY KEY,
            symbol TEXT NOT NULL,
            market TEXT NOT NULL DEFAULT 'stock',
            condition TEXT NOT NULL CHECK (condition IN ('above', 'below')),
            target_price DOUBLE PRECISION NOT NULL,
            note TEXT,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'paused', 'triggered', 'cancelled')),
            created_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'utc', 'YYYY-MM-DD HH24:MI:SS'),
            triggered_at TEXT,
            last_checked_price DOUBLE PRECISION
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS alert_events (
            id BIGSERIAL PRIMARY KEY,
            alert_id INTEGER NOT NULL REFERENCES price_alerts(id),
            symbol TEXT NOT NULL,
            price DOUBLE PRECISION NOT NULL,
            target_price DOUBLE PRECISION NOT NULL,
            condition TEXT NOT NULL,
            fired_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'utc', 'YYYY-MM-DD HH24:MI:SS'),
            delivered_via TEXT NOT NULL DEFAULT 'log'
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_price_alerts_active ON price_alerts(status, symbol)",
        "CREATE INDEX IF NOT EXISTS idx_alert_events_alert ON alert_events(alert_id)",
    ],
}


def _apply_sqlite(path: Path) -> List[str]:
    """Legacy path: explicit SQLite file (tests pass temp paths)."""
    import sqlite3

    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    try:
        for stmt in _SCHEMA["sqlite"]:
            con.execute(stmt)
        con.commit()
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        con.close()


def ensure_tables(db_path: Optional[Union[str, Path]] = None) -> List[str]:
    """Apply the schema.

    db_path=None (default) -> central adapter (SQLite locally, Postgres
    when DATABASE_URL is set). Pass an explicit path to force SQLite at
    that location (used by tests).
    """
    if db_path is not None:
        return _apply_sqlite(Path(db_path))
    adapter = get_adapter()
    stmts = _SCHEMA["postgres" if adapter.is_postgres else "sqlite"]
    for stmt in stmts:
        adapter.execute(stmt)
    return adapter.list_tables()
