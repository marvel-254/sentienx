"""Unified quote layer for SENTIENX (OpenStock-derived).

One interface, two markets:

* ``stock`` -> Finnhub REST API (the same provider OpenStock uses)
* ``deriv`` -> Deriv (adapter over the existing deriv_connector.py /
  ws_client.py work; tick streaming lands in Phase 2)

This core module is stdlib-only so it runs in any of the project venvs.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Protocol, Union

FINNHUB_BASE = "https://finnhub.io/api/v1"


@dataclass
class Quote:
    symbol: str
    market: str  # 'stock' | 'deriv'
    price: Optional[float]
    change: Optional[float]        # absolute change
    change_percent: Optional[float]
    high: Optional[float] = None
    low: Optional[float] = None
    open: Optional[float] = None
    previous_close: Optional[float] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    source: str = "unknown"
    stale: bool = True

    @property
    def direction(self) -> str:
        if self.change is None or self.change == 0:
            return "flat"
        return "up" if self.change > 0 else "down"


class QuoteProvider(Protocol):
    def get_quote(self, symbol: str) -> Quote: ...
    def search(self, query: str) -> List[dict]: ...


class FinnhubProvider:
    """Finnhub REST quotes.

    Free tier: US stocks, delayed data, 60 API calls/minute. Callers that
    sweep many symbols (alerts, heatmap) should batch and cache.
    """

    market = "stock"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("FINNHUB_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "Finnhub API key missing. Set FINNHUB_API_KEY in .env "
                "or pass api_key= to FinnhubProvider()."
            )

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        query = dict(params or {})
        query["token"] = self.api_key
        url = f"{FINNHUB_BASE}/{path}?{urllib.parse.urlencode(query)}"
        req = urllib.request.Request(
            url, headers={"User-Agent": "sentienx-openstock/0.1"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def get_quote(self, symbol: str) -> Quote:
        raw = self._get("quote", {"symbol": symbol})
        price = raw.get("c")
        return Quote(
            symbol=symbol,
            market=self.market,
            price=price,
            change=raw.get("d"),
            change_percent=raw.get("dp"),
            high=raw.get("h"),
            low=raw.get("l"),
            open=raw.get("o"),
            previous_close=raw.get("pc"),
            source="finnhub",
            stale=price in (None, 0),
        )

    def search(self, query: str) -> List[dict]:
        raw = self._get("search", {"q": query})
        return raw.get("result", [])


class DerivProvider:
    """Deriv quotes.

    Phase 2 wires live ticks through ws_client.py. v1 exposes the
    adapter seam and returns stale quotes so the rest of the package
    (watchlist, alerts, palette) can be built against it now.
    """

    market = "deriv"

    def __init__(self):
        try:
            from deriv_connector import DerivConnector  # existing SENTIENX module
        except ImportError as exc:  # pragma: no cover - depends on cwd
            raise ImportError(
                "deriv_connector.py not importable; run from the SENTIENX root"
            ) from exc
        self._connector = DerivConnector()

    def get_quote(self, symbol: str) -> Quote:
        # Phase 2: subscribe to ticks via ws_client.py. Until then, no price.
        return Quote(
            symbol=symbol,
            market=self.market,
            price=None,
            change=None,
            change_percent=None,
            source="deriv",
            stale=True,
        )

    def search(self, query: str) -> List[dict]:
        return [{"symbol": query.upper(), "market": self.market, "source": "deriv-static"}]


def get_provider(market: str, api_key: Optional[str] = None) -> QuoteProvider:
    if market == "stock":
        return FinnhubProvider(api_key)
    if market == "deriv":
        return DerivProvider()
    raise ValueError(f"unknown market: {market!r} (expected 'stock' or 'deriv')")
