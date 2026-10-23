"""Per-symbol watchlist backed by the SENTIENX SQLite database.

Port of OpenStock's watchlist (database/models/watchlist.model.ts +
lib/actions/watchlist.actions.ts) from MongoDB to sqlite3. SENTIENX is
single-user, so there is no user_id column.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Optional, Union

from .migrations import DEFAULT_DB_PATH, ensure_tables


class WatchlistRepository:
    def __init__(self, db_path: Union[str, Path] = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        ensure_tables(self.db_path)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.db_path))
        con.row_factory = sqlite3.Row
        return con

    def add(
        self,
        symbol: str,
        market: str = "stock",
        display_name: Optional[str] = None,
        note: Optional[str] = None,
    ) -> bool:
        """Add a symbol. Returns False if it was already on the list."""
        symbol = symbol.strip().upper()
        with self._connect() as con:
            cur = con.execute(
                "INSERT OR IGNORE INTO watchlist (symbol, market, display_name, note) "
                "VALUES (?, ?, ?, ?)",
                (symbol, market, display_name, note),
            )
            return cur.rowcount > 0

    def remove(self, symbol: str, market: Optional[str] = None) -> bool:
        symbol = symbol.strip().upper()
        query = "DELETE FROM watchlist WHERE symbol = ?"
        params: List = [symbol]
        if market:
            query += " AND market = ?"
            params.append(market)
        with self._connect() as con:
            cur = con.execute(query, params)
            return cur.rowcount > 0

    def list(self, market: Optional[str] = None) -> List[dict]:
        query = "SELECT * FROM watchlist"
        params: List = []
        if market:
            query += " WHERE market = ?"
            params.append(market)
        query += " ORDER BY added_at DESC, symbol"
        with self._connect() as con:
            rows = con.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def has(self, symbol: str, market: Optional[str] = None) -> bool:
        symbol = symbol.strip().upper()
        query = "SELECT 1 FROM watchlist WHERE symbol = ?"
        params: List = [symbol]
        if market:
            query += " AND market = ?"
            params.append(market)
        with self._connect() as con:
            return con.execute(query, params).fetchone() is not None
