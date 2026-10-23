"""Market session clock (port of OpenStock's lib/market-session.ts + markets.ts).

Deriv synthetic/forex markets trade around the clock; equities follow
exchange hours. All comparisons are timezone-aware via zoneinfo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Dict, Optional, Tuple
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Exchange:
    code: str
    name: str
    tz: str
    open_time: time
    close_time: time
    weekend: Tuple[int, ...] = (5, 6)  # Saturday, Sunday by default


EXCHANGES: Dict[str, Exchange] = {
    "NYSE": Exchange("NYSE", "New York Stock Exchange", "America/New_York",
                     time(9, 30), time(16, 0)),
    "NASDAQ": Exchange("NASDAQ", "Nasdaq", "America/New_York",
                       time(9, 30), time(16, 0)),
    "LSE": Exchange("LSE", "London Stock Exchange", "Europe/London",
                    time(8, 0), time(16, 30)),
    "JPX": Exchange("JPX", "Tokyo Stock Exchange", "Asia/Tokyo",
                    time(9, 0), time(15, 0)),
    "DERIV": Exchange("DERIV", "Deriv (synthetics/forex)", "UTC",
                      time(0, 0), time(23, 59, 59), weekend=()),
}


def is_market_open(exchange_code: str, at: Optional[datetime] = None) -> bool:
    """True when the exchange is in session at ``at`` (default: now).

    Naive datetimes are interpreted in the exchange's local timezone.
    Note: public holidays are not modelled in v1.
    """
    exchange = EXCHANGES[exchange_code.upper()]
    moment = at or datetime.now(tz=ZoneInfo(exchange.tz))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=ZoneInfo(exchange.tz))
    local = moment.astimezone(ZoneInfo(exchange.tz))
    if local.weekday() in exchange.weekend:
        return False
    minutes = local.hour * 60 + local.minute
    open_m = exchange.open_time.hour * 60 + exchange.open_time.minute
    close_m = exchange.close_time.hour * 60 + exchange.close_time.minute
    return open_m <= minutes <= close_m


def market_status_line(exchange_code: str, at: Optional[datetime] = None) -> str:
    exchange = EXCHANGES[exchange_code.upper()]
    state = "OPEN" if is_market_open(exchange_code, at) else "CLOSED"
    return f"{exchange.name}: {state}"
