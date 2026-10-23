"""Per-symbol watchlist backed by the central SENTIENX adapter.

Port of OpenStock's watchlist (database/models/watchlist.model.ts +
lib/actions/watchlist.actions.ts) from MongoDB. SENTIENX is
single-user, so there is no user_id column.

Uses core.db_adapter: PostgreSQL when DATABASE_URL is set (Render),
SQLite locally. Tests may pass an explicit db_path to pin SQLite.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union

try:
    from core.db_adapter import DatabaseAdapter, get_adapter
except ImportError:
    from .db_adapter import DatabaseAdapter, get_adapter

from .migrations import DEFAULT_DB_PATH, ensure_tables


class WatchlistRepository:
    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        if db_path is None:
            self.adapter = get_adapter()
        else:
            self.adapter = DatabaseAdapter(sqlite_path=db_path)
        ensure_tables(db_path)

    def add(
        self,
        symbol: str,
        market: str = "stock",
        display_name: Optional[str] = None,
        note: Optional[str] = None,
    ) -> bool:
        """Add a symbol. Returns False if it was already on the list."""
        symbol = symbol.strip().upper()
        sql = (
            "INSERT OR IGNORE INTO watchlist (symbol, market, display_name, note) "
            "VALUES (?, ?, ?, ?)"
        )
        if self.adapter.is_postgres:
            sql = sql.replace("INSERT OR IGNORE INTO watchlist", "INSERT INTO watchlist")
            sql += " ON CONFLICT (symbol, market) DO NOTHING"
        cur_rowcount = self.adapter.execute(sql, (symbol, market, display_name, note))
        return bool(cur_rowcount)

    def remove(self, symbol: str, market: Optional[str] = None) -> bool:
        symbol = symbol.strip().upper()
        query = "DELETE FROM watchlist WHERE symbol = ?"
        params: List = [symbol]
        if market:
            query += " AND market = ?"
            params.append(market)
        return bool(self.adapter.execute(query, params))

    def list(self, market: Optional[str] = None) -> List[dict]:
        query = "SELECT * FROM watchlist"
        params: List = []
        if market:
            query += " WHERE market = ?"
            params.append(market)
        query += " ORDER BY added_at DESC, symbol"
        return self.adapter.fetchall(query, params)

    def has(self, symbol: str, market: Optional[str] = None) -> bool:
        symbol = symbol.strip().upper()
        query = "SELECT 1 FROM watchlist WHERE symbol = ?"
        params: List = [symbol]
        if market:
            query += " AND market = ?"
            params.append(market)
        return self.adapter.fetchone(query, params) is not None
