#!/usr/bin/env python3
"""Copy existing SQLite data into PostgreSQL.

Usage:
    DATABASE_URL=postgresql://... .venv/bin/python scripts/migrate_sqlite_to_postgres.py
    DATABASE_URL=... .venv/bin/python scripts/migrate_sqlite_to_postgres.py --source path/to/sentienx_trading.db

Copies trading_history, signals_history, watchlist, price_alerts and
alert_events from a SQLite file into the database resolved by
DATABASE_URL (via core.db_adapter). Tables are created if missing and
rows are inserted only if the target table is empty (safe to re-run).
"""

import argparse
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from core.db_adapter import DatabaseAdapter, get_adapter  # noqa: E402
from openstock.migrations import ensure_tables  # noqa: E402

DEFAULT_SQLITE = _SRC.parent / "sentienx_trading.db"  # legacy root-level DB with the data

# table -> list of columns (id excluded; target reassigns ids)
TABLES = {
    "trading_history": ["symbol", "direction", "entry_price", "exit_price",
                        "volume", "profit_loss", "status", "timestamp", "strategy"],
    "signals_history": ["symbol", "signal", "confidence", "strength",
                        "indicators", "timestamp", "strategy"],
    "watchlist": ["symbol", "market", "display_name", "added_at", "note"],
    "price_alerts": ["symbol", "market", "condition", "target_price", "note",
                     "status", "created_at", "triggered_at", "last_checked_price"],
    "alert_events": ["alert_id", "symbol", "price", "target_price",
                     "condition", "fired_at", "delivered_via"],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(DEFAULT_SQLITE),
                        help="SQLite source file (default: repo sentienx_trading.db)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    source_db = Path(args.source)
    if not source_db.exists():
        print(f"Source SQLite not found: {source_db}")
        return 1

    import sqlite3

    src = sqlite3.connect(str(source_db))
    src.row_factory = sqlite3.Row

    target = get_adapter()
    if not target.is_postgres:
        print("DATABASE_URL is not set - refusing to copy SQLite onto itself.")
        return 2

    target.ensure_schema()
    ensure_tables(None)

    total = 0
    for table, cols in TABLES.items():
        src_cols = {r[1] for r in src.execute(f"PRAGMA table_info({table})")}
        if not src_cols:
            if args.verbose:
                print(f"{table}: not present in source, skipped")
            continue

        count = src.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if count == 0:
            if args.verbose:
                print(f"{table}: source empty, skipped")
            continue

        dest_count = target.fetchone(f"SELECT COUNT(*) as c FROM {table}")["c"]
        if dest_count:
            print(f"{table}: target already has {dest_count} row(s), skipped")
            continue

        usable = [c for c in cols if c in src_cols]
        rows = src.execute(
            f"SELECT {', '.join(usable)} FROM {table}"
        ).fetchall()
        ph = ", ".join("?" for _ in usable)
        sql = f"INSERT INTO {table} ({', '.join(usable)}) VALUES ({ph})"
        for row in rows:
            target.insert(sql, tuple(row[c] for c in usable))
        total += len(rows)
        print(f"{table}: copied {len(rows)} row(s)")

    src.close()
    print(f"Done. {total} row(s) copied into {target._database_url.split('@')[-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
