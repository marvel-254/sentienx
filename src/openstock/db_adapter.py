"""Database adapter: SQLite (local dev) or Postgres (Render/Neon).

Resolution order:
  1. DATABASE_URL env var (Postgres on Render/Neon)
  2. SENTIENX_DB_PATH env var (SQLite override)
  3. Default: src/sentienx_trading.db (SQLite)
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Optional, Union

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False
    psycopg2 = None  # type: ignore
    RealDictCursor = None  # type: ignore

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "sentienx_trading.db"


class DatabaseAdapter:
    """Unified connection factory for SQLite and PostgreSQL."""

    def __init__(self, database_url: Optional[str] = None, sqlite_path: Optional[Union[str, Path]] = None):
        self._database_url = database_url or os.environ.get("DATABASE_URL", "")
        self._sqlite_path = Path(sqlite_path or os.environ.get("SENTIENX_DB_PATH", str(DEFAULT_DB_PATH)))
        self._is_postgres = bool(self._database_url)
        
        if self._is_postgres and not HAS_PSYCOPG2:
            raise RuntimeError(
                "DATABASE_URL is set but psycopg2 is not installed. "
                "Install with: pip install psycopg2-binary"
            )

    @property
    def is_postgres(self) -> bool:
        return self._is_postgres

    @property
    def sqlite_path(self) -> Path:
        return self._sqlite_path

    @contextmanager
    def connect(self) -> Generator[Any, None, None]:
        """Context manager that yields a database connection."""
        if self._is_postgres:
            con = psycopg2.connect(self._database_url, cursor_factory=RealDictCursor)
            try:
                yield con
            finally:
                con.close()
        else:
            self._sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            con = sqlite3.connect(str(self._sqlite_path))
            con.row_factory = sqlite3.Row
            try:
                yield con
            finally:
                con.close()

    def execute(self, query: str, params: tuple = ()) -> Any:
        """Execute a query and return cursor (for SELECT) or rowcount/lastrowid."""
        with self.connect() as con:
            cur = con.execute(query, params)
            if query.strip().upper().startswith("SELECT"):
                return cur.fetchall()
            con.commit()
            return cur

    def execute_many(self, query: str, params_list: list) -> None:
        """Execute a query multiple times with different parameters."""
        with self.connect() as con:
            con.executemany(query, params_list)
            con.commit()

    def fetchone(self, query: str, params: tuple = ()) -> Optional[dict]:
        """Fetch a single row as dict."""
        with self.connect() as con:
            cur = con.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row else None

    def fetchall(self, query: str, params: tuple = ()) -> list[dict]:
        """Fetch all rows as list of dicts."""
        with self.connect() as con:
            cur = con.execute(query, params)
            return [dict(r) for r in cur.fetchall()]

    def lastrowid(self, query: str, params: tuple = ()) -> Optional[int]:
        """Execute INSERT and return lastrowid (SQLite) or RETURNING id (Postgres)."""
        with self.connect() as con:
            if self._is_postgres:
                # For Postgres, append RETURNING id
                if "RETURNING" not in query.upper():
                    query = query.rstrip(";") + " RETURNING id"
                cur = con.execute(query, params)
                row = cur.fetchone()
                return row["id"] if row else None
            else:
                cur = con.execute(query, params)
                return cur.lastrowid

    def adapt_query(self, query: str) -> str:
        """Adapt SQLite-specific syntax to PostgreSQL."""
        if not self._is_postgres:
            return query
        
        # Replace SQLite-specific syntax
        adapted = query
        
        # AUTOINCREMENT -> SERIAL
        adapted = adapted.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        adapted = adapted.replace("AUTOINCREMENT", "")
        
        # datetime('now') -> CURRENT_TIMESTAMP
        adapted = adapted.replace("datetime('now')", "CURRENT_TIMESTAMP")
        adapted = adapted.replace("(datetime('now'))", "CURRENT_TIMESTAMP")
        
        # IF NOT EXISTS for indexes (PostgreSQL supports this)
        # Already supported in both
        
        # BOOLEAN handling - SQLite uses 0/1, Postgres uses TRUE/FALSE
        adapted = adapted.replace("= 1", "= TRUE").replace("= 0", "= FALSE")
        
        # LIMIT ? OFFSET ? -> LIMIT ? OFFSET ? (same in both)
        
        return adapted

    def adapt_params(self, params: tuple) -> tuple:
        """Adapt parameters for PostgreSQL (e.g., boolean conversion)."""
        if not self._is_postgres:
            return params
        
        adapted = []
        for p in params:
            if isinstance(p, bool):
                adapted.append(p)
            else:
                adapted.append(p)
        return tuple(adapted)

    def execute_adapted(self, query: str, params: tuple = ()) -> Any:
        """Execute a query with adapted syntax for the target database."""
        adapted_query = self.adapt_query(query)
        adapted_params = self.adapt_params(params)
        return self.execute(adapted_query, adapted_params)

    def fetchone_adapted(self, query: str, params: tuple = ()) -> Optional[dict]:
        """Fetch a single row with adapted query."""
        adapted_query = self.adapt_query(query)
        adapted_params = self.adapt_params(params)
        return self.fetchone(adapted_query, adapted_params)

    def fetchall_adapted(self, query: str, params: tuple = ()) -> list[dict]:
        """Fetch all rows with adapted query."""
        adapted_query = self.adapt_query(query)
        adapted_params = self.adapt_params(params)
        return self.fetchall(adapted_query, adapted_params)

    def execute_many_adapted(self, query: str, params_list: list) -> None:
        """Execute many with adapted query."""
        adapted_query = self.adapt_query(query)
        adapted_params_list = [self.adapt_params(p) for p in params_list]
        self.execute_many(adapted_query, adapted_params_list)


def get_database_adapter(
    database_url: Optional[str] = None,
    sqlite_path: Optional[Union[str, Path]] = None
) -> DatabaseAdapter:
    """Factory function to get a DatabaseAdapter instance."""
    return DatabaseAdapter(database_url, sqlite_path)


def get_database_url() -> str:
    """Return DATABASE_URL if set, else empty string (SQLite mode)."""
    return os.environ.get("DATABASE_URL", "")


def is_postgres() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


def get_sqlite_path() -> Path:
    return Path(os.environ.get("SENTIENX_DB_PATH", str(DEFAULT_DB_PATH)))


# Backward compatibility - global default adapter
_default_adapter: Optional[DatabaseAdapter] = None


def get_default_adapter() -> DatabaseAdapter:
    """Get or create the default global adapter."""
    global _default_adapter
    if _default_adapter is None:
        _default_adapter = DatabaseAdapter()
    return _default_adapter