"""Canonical database adapter for SENTIENX.

One connection layer for every DB consumer (dashboard, API, OpenStock
modules). Resolution order:

  1. DATABASE_URL env var          -> PostgreSQL (Render / Neon / local Docker)
  2. SENTIENX_DB_PATH env var      -> SQLite at that path
  3. Default: src/sentienx_trading.db (SQLite, unchanged local behaviour)

Set DATABASE_URL on Render to deploy with Postgres; leave it unset
locally and everything keeps working with SQLite.

Notes for Postgres mode:
  * SQLite-style ``?`` placeholders are translated to ``%s`` for
    psycopg2 (no literal ``?`` is used in SENTIENX queries).
  * Rows are always dict-like (RealDictCursor on Postgres,
    sqlite3.Row converted via dict() helpers here).
  * Timestamps stay TEXT/ISO strings so callers that slice strings
    (e.g. ``row["timestamp"][:16]``) keep working.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, List, Optional, Sequence, Union


try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False
    psycopg2 = None
    RealDictCursor = None


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "sentienx_trading.db"


class DatabaseAdapter:
    """Unified connection factory for SQLite and PostgreSQL."""

    def __init__(
        self,
        database_url: Optional[str] = None,
        sqlite_path: Optional[Union[str, Path]] = None,
    ):
        url = database_url or os.environ.get("DATABASE_URL", "")
        url = url.strip()
        # Normalise URI schemes so psycopg2 always accepts them
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        self._database_url = url
        self._sqlite_path = Path(
            sqlite_path or os.environ.get("SENTIENX_DB_PATH", str(DEFAULT_DB_PATH))
        )
        self._is_postgres = bool(self._database_url)

        if self._is_postgres and not HAS_PSYCOPG2:
            raise RuntimeError(
                "DATABASE_URL is set but psycopg2 is not installed. "
                "Install with: pip install psycopg2-binary"
            )

    # -- properties -----------------------------------------------------

    @property
    def is_postgres(self) -> bool:
        return self._is_postgres

    @property
    def sqlite_path(self) -> Path:
        return self._sqlite_path

    # -- internals ------------------------------------------------------

    def _norm(self, sql: str) -> str:
        """Translate SQLite `?` placeholders for psycopg2 (%s)."""
        if self._is_postgres:
            return sql.replace("?", "%s")
        return sql

    @staticmethod
    def _is_select(sql: str) -> bool:
        return sql.lstrip().upper().startswith("SELECT")

    # -- connection -----------------------------------------------------

    @contextmanager
    def connect(self) -> Generator[Any, None, None]:
        """Yield a DBAPI connection. Auto-commits on success, rolls
        back on exception, always closes."""
        if self._is_postgres:
            con = psycopg2.connect(self._database_url, cursor_factory=RealDictCursor)
            try:
                yield con
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()
        else:
            self._sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            con = sqlite3.connect(str(self._sqlite_path))
            con.row_factory = sqlite3.Row
            try:
                con.execute("PRAGMA journal_mode=WAL")
            except sqlite3.Error:
                pass  # non-critical
            try:
                yield con
                con.commit()
            except Exception:
                try:
                    con.rollback()
                except sqlite3.Error:
                    pass
                raise
            finally:
                con.close()

    # -- one-shot helpers ------------------------------------------------

    def execute(self, sql: str, params: Optional[Sequence] = None) -> Any:
        """Run SQL. SELECT -> list of dict-like rows; else -> rowcount."""
        sql = self._norm(sql)
        params = tuple(params or ())
        with self.connect() as con:
            cur = con.cursor()
            cur.execute(sql, params)
            if self._is_select(sql):
                return cur.fetchall()
            return cur.rowcount

    def fetchone(self, sql: str, params: Optional[Sequence] = None) -> Optional[dict]:
        """Fetch a single row as a plain dict (None if absent)."""
        sql = self._norm(sql)
        params = tuple(params or ())
        with self.connect() as con:
            cur = con.cursor()
            cur.execute(sql, params)
            row = cur.fetchone()
            return dict(row) if row is not None else None

    def fetchall(self, sql: str, params: Optional[Sequence] = None) -> List[dict]:
        """Fetch all rows as a list of plain dicts."""
        sql = self._norm(sql)
        params = tuple(params or ())
        with self.connect() as con:
            cur = con.cursor()
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def insert(self, sql: str, params: Optional[Sequence] = None) -> Optional[int]:
        """INSERT a row and return its id (SQLite lastrowid /
        Postgres RETURNING id)."""
        sql = self._norm(sql)
        params = tuple(params or ())
        with self.connect() as con:
            cur = con.cursor()
            if self._is_postgres:
                if "returning" not in sql.lower():
                    sql = sql.rstrip("; ") + " RETURNING id"
                cur.execute(sql, params)
                row = cur.fetchone()
                return row["id"] if row else None
            cur.execute(sql, params)
            return cur.lastrowid

    def read_df(self, sql: str, params: Optional[Sequence] = None):
        """Run a SELECT and return a pandas DataFrame (handles the
        ``?``/``%s`` placeholder difference internally)."""
        import pandas as pd

        sql = self._norm(sql)
        params = tuple(params or ())
        with self.connect() as con:
            return pd.read_sql_query(sql, con, params=params)

    # -- dialect helpers --------------------------------------------------

    def date_expr(self, column_sql: str) -> str:
        """SQL for the calendar-date part of a TEXT/timestamp column."""
        if self._is_postgres:
            return f"({column_sql})::date"
        return f"DATE({column_sql})"

    def default_now_expr(self) -> str:
        """DEFAULT expression producing an ISO 'YYYY-MM-DD HH:MM:SS'
        string in both dialects."""
        if self._is_postgres:
            return "to_char(now() AT TIME ZONE 'utc', 'YYYY-MM-DD HH24:MI:SS')"
        return "datetime('now')"

    # -- schema -----------------------------------------------------------

    CORE_SCHEMA = {
        "sqlite": [
            """
            CREATE TABLE IF NOT EXISTS trading_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                direction TEXT,
                entry_price REAL,
                exit_price REAL,
                volume REAL,
                profit_loss REAL,
                status TEXT,
                timestamp TEXT,
                strategy TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS signals_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                signal TEXT,
                confidence REAL,
                strength REAL,
                indicators TEXT,
                timestamp TEXT,
                strategy TEXT
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_trading_history_ts
            ON trading_history(timestamp)
            """,
        ],
        "postgres": [
            """
            CREATE TABLE IF NOT EXISTS trading_history (
                id BIGSERIAL PRIMARY KEY,
                symbol TEXT,
                direction TEXT,
                entry_price DOUBLE PRECISION,
                exit_price DOUBLE PRECISION,
                volume DOUBLE PRECISION,
                profit_loss DOUBLE PRECISION,
                status TEXT,
                timestamp TEXT,
                strategy TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS signals_history (
                id BIGSERIAL PRIMARY KEY,
                symbol TEXT,
                signal TEXT,
                confidence DOUBLE PRECISION,
                strength DOUBLE PRECISION,
                indicators TEXT,
                timestamp TEXT,
                strategy TEXT
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_trading_history_ts
            ON trading_history(timestamp)
            """,
        ],
    }

    def ensure_schema(self) -> List[str]:
        """Create the core SENTIENX tables (idempotent). Returns the
        list of table names present afterwards."""
        stmts = self.CORE_SCHEMA["postgres" if self._is_postgres else "sqlite"]
        with self.connect() as con:
            cur = con.cursor()
            for stmt in stmts:
                cur.execute(stmt)
        return self.list_tables()

    def list_tables(self) -> List[str]:
        with self.connect() as con:
            cur = con.cursor()
            if self._is_postgres:
                cur.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' ORDER BY table_name"
                )
                return sorted(r["table_name"] for r in cur.fetchall())
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            rows = cur.fetchall()
            return [r["name"] for r in rows]


# -- module-level convenience --------------------------------------------


_adapter: Optional[DatabaseAdapter] = None


def get_adapter() -> DatabaseAdapter:
    """Singleton adapter resolved from the environment at first use."""
    global _adapter
    if _adapter is None:
        _adapter = DatabaseAdapter()
    return _adapter


def reset_adapter(database_url: Optional[str] = None,
                  sqlite_path: Optional[Union[str, Path]] = None) -> None:
    """Replace the singleton (mainly for tests)."""
    global _adapter
    _adapter = DatabaseAdapter(database_url, sqlite_path)


def is_postgres() -> bool:
    return bool(os.environ.get("DATABASE_URL", "").strip())


def get_sqlite_path() -> Path:
    return Path(os.environ.get("SENTIENX_DB_PATH", str(DEFAULT_DB_PATH)))
