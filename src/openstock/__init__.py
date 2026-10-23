"""SENTIENX openstock package.

Features ported from OpenStock (https://github.com/Open-Dev-Society/OpenStock,
AGPL-3.0 (c) Open Dev Society). See docs/OPENSTOCK_MERGE_PLAN.md for the full
merge plan and openstock/README.md for license attribution.

Core modules are stdlib-only so they run in any of the project venvs.
UI helpers (heatmap, palette, tradingview, streamlit_pages) import
streamlit lazily. demo.py supplies deterministic placeholder quotes so the
dashboard works with zero API keys.
"""

from .migrations import ensure_tables
from .quotes import Quote, FinnhubProvider, DerivProvider, get_provider
from .demo import DemoProvider, DEFAULT_SYMBOLS, demo_price
from .watchlist import WatchlistRepository
from .alerts import Alert, AlertRepository, evaluate_rule
from .notifiers import DesktopNotifier, CompositeNotifier, make_notifier
from .market_clock import EXCHANGES, is_market_open, market_status_line
from .palette import Action, ActionRegistry
from .heatmap import heat_color

__all__ = [
    "ensure_tables",
    "Quote",
    "FinnhubProvider",
    "DerivProvider",
    "get_provider",
    "DemoProvider",
    "DEFAULT_SYMBOLS",
    "demo_price",
    "WatchlistRepository",
    "Alert",
    "AlertRepository",
    "evaluate_rule",
    "DesktopNotifier",
    "CompositeNotifier",
    "make_notifier",
    "EXCHANGES",
    "is_market_open",
    "market_status_line",
    "Action",
    "ActionRegistry",
    "heat_color",
]
