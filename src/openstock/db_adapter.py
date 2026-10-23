"""Deprecated shim — canonical adapter now lives in core.db_adapter.

Everything here re-exports from src/core/db_adapter.py so existing
imports (openstock.db_adapter) keep working.
"""
from __future__ import annotations

try:
    from core.db_adapter import (  # noqa: F401
        DEFAULT_DB_PATH,
        HAS_PSYCOPG2,
        DatabaseAdapter,
        get_adapter,
        get_sqlite_path,
        is_postgres,
        reset_adapter,
    )
except ImportError:  # when src/ itself is the sys.path root
    import os
    import sys
    from pathlib import Path

    _src = Path(__file__).resolve().parent.parent
    if str(_src) not in sys.path:
        sys.path.insert(0, str(_src))
    from core.db_adapter import (  # noqa: F401
        DEFAULT_DB_PATH,
        HAS_PSYCOPG2,
        DatabaseAdapter,
        get_adapter,
        get_sqlite_path,
        is_postgres,
        reset_adapter,
    )
