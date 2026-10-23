"""Deterministic demo quotes — the dashboard works with zero API keys.

Prices follow a smooth deterministic walk (sum of sines seeded per symbol),
so the UI is stable across reruns but still drifts over time (5-minute
buckets). Every surface labels this data as ``demo``. It is replaced
automatically by FinnhubProvider once FINNHUB_API_KEY is set in .env.
"""

from __future__ import annotations

import math
import time
import zlib
from typing import Dict, List, Optional

from .quotes import Quote

STOCK_SYMBOLS = (
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "TSLA", "META", "AMD", "SPY", "QQQ",
)
DERIV_SYMBOLS = (
    "R_10", "R_25", "R_50", "R_75", "R_100",
    "BOOM500", "BOOM1000", "CRASH500", "CRASH1000", "VOL75",
)

DEFAULT_SYMBOLS = tuple((s, "stock") for s in STOCK_SYMBOLS) + tuple(
    (s, "deriv") for s in DERIV_SYMBOLS
)

_BASE_PRICES: Dict[str, float] = {
    "AAPL": 232.40, "MSFT": 428.10, "NVDA": 138.60, "GOOGL": 178.30,
    "AMZN": 214.50, "TSLA": 342.70, "META": 596.20, "AMD": 162.90,
    "SPY": 585.10, "QQQ": 512.40,
    "R_10": 6412.0, "R_25": 3187.0, "R_50": 1543.0, "R_75": 923.5,
    "R_100": 5612.0, "BOOM500": 8741.0, "BOOM1000": 9312.0,
    "CRASH500": 4418.0, "CRASH1000": 5126.0, "VOL75": 512340.0,
}

BUCKET_SECONDS = 300  # one demo "tick" every 5 minutes
DAY_BUCKETS = 288     # 24h of 5-minute buckets


def _phase(symbol: str, salt: int) -> float:
    return (zlib.crc32(f"{symbol}:{salt}".encode()) % 1000) / 1000.0 * 2 * math.pi


def _base_price(symbol: str) -> float:
    if symbol in _BASE_PRICES:
        return _BASE_PRICES[symbol]
    # Stable pseudo-price for unknown symbols: 12.00 - 620.00.
    return 12.0 + (zlib.crc32(symbol.encode()) % 60800) / 100.0


def demo_price(symbol: str, bucket: int) -> float:
    """Deterministic price for ``symbol`` at 5-minute bucket ``bucket``."""
    base = _base_price(symbol)
    wave = (
        0.020 * math.sin(bucket / 9.0 + _phase(symbol, 1))
        + 0.012 * math.sin(bucket / 3.7 + _phase(symbol, 2))
        + 0.006 * math.sin(bucket / 1.9 + _phase(symbol, 3))
    )
    return round(base * (1.0 + wave), 4)


def current_bucket(now: Optional[float] = None) -> int:
    return int((now if now is not None else time.time()) // BUCKET_SECONDS)


class DemoProvider:
    """QuoteProvider backed by deterministic demo prices (source='demo')."""

    def __init__(self, deriv_symbols=DERIV_SYMBOLS):
        self._deriv = set(deriv_symbols)

    def market_for(self, symbol: str) -> str:
        return "deriv" if symbol.strip().upper() in self._deriv else "stock"

    def get_quote(self, symbol: str) -> Quote:
        symbol = symbol.strip().upper()
        bucket = current_bucket()
        price = demo_price(symbol, bucket)
        open_price = demo_price(symbol, bucket - (bucket % DAY_BUCKETS))
        prev_close = demo_price(
            symbol, bucket - (bucket % DAY_BUCKETS) - DAY_BUCKETS
        )
        change = round(price - prev_close, 4)
        change_percent = round((change / prev_close) * 100.0, 2) if prev_close else 0.0
        return Quote(
            symbol=symbol,
            market=self.market_for(symbol),
            price=price,
            change=change,
            change_percent=change_percent,
            high=round(price * 1.003, 4),
            low=round(price * 0.997, 4),
            open=open_price,
            previous_close=prev_close,
            source="demo",
            stale=False,
        )

    def search(self, query: str) -> List[dict]:
        q = (query or "").strip().upper()
        return [
            {"symbol": s, "market": m, "source": "demo"}
            for s, m in DEFAULT_SYMBOLS
            if not q or q in s
        ]
