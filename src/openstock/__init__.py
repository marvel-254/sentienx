"""SENTIENX openstock package.

Features ported from OpenStock (https://github.com/Open-Dev-Society/OpenStock,
AGPL-3.0 (c) Open Dev Society). See OPENSTOCK_MERGE_PLAN.md at the SENTIENX
root for the full merge plan and openstock/README.md for license attribution.

Core modules are stdlib-only so they run in any of the project venvs.
UI helpers (heatmap, palette, tradingview) import streamlit lazily.
"""

from .migrations import ensure_tables
from .quotes import Quote, FinnhubProvider, DerivProvider, get_provider
from .watchlist import WatchlistRepository
from .alerts import Alert, AlertRepository, evaluate_rule
from .market_clock import EXCHANGES, is_market_open, market_status_line
from .palette import Action, ActionRegistry

__all__ = [
    "ensure_tables",
    "Quote",
    "FinnhubProvider",
    "DerivProvider",
    "get_provider",
    "WatchlistRepository",
    "Alert",
    "AlertRepository",
    "evaluate_rule",
    "EXCHANGES",
    "is_market_open",
    "market_status_line",
    "Action",
    "ActionRegistry",
]
