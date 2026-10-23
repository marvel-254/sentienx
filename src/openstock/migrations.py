"""Additive SQLite migrations for OpenStock-derived features.

Creates the tables needed by the openstock package (watchlist,
price_alerts, alert_events) inside the existing SENTIENX database.
Every statement is CREATE TABLE IF NOT EXISTS, so running this is
idempotent and safe to call from any entry point. The existing
trading_history table is never touched.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Union

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "sentienx_trading.db"

SCHEMA = [
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
]


def ensure_tables(db_path: Union[str, Path] = DEFAULT_DB_PATH) -> List[str]:
    """Apply the schema. Returns the list of table names present afterwards."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    try:
        for stmt in SCHEMA:
            con.execute(stmt)
        con.commit()
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        con.close()
