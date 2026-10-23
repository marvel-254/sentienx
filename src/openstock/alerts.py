"""Price alerts (port of OpenStock's alert model + alert.actions).

OpenStock evaluates alerts server-side on an Inngest cron. SENTIENX is
single-user and local, so evaluation is a plain function the dashboard
or a background thread can call on a timer (Phase 2).

Pure rule logic lives in evaluate_rule() so it is trivially testable.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Protocol, Union

from .migrations import DEFAULT_DB_PATH, ensure_tables
from .quotes import Quote

VALID_CONDITIONS = ("above", "below")
VALID_STATUSES = ("active", "paused", "triggered", "cancelled")


def evaluate_rule(price: float, condition: str, target: float) -> bool:
    """True when the alert condition is met. condition: 'above' | 'below'."""
    if condition == "above":
        return price >= target
    if condition == "below":
        return price <= target
    raise ValueError(f"unknown condition: {condition!r}")


class Notifier(Protocol):
    def deliver(self, alert: "Alert", quote: Quote) -> str: ...


class LogNotifier:
    """Default notifier: log line only. Phase 3 adds email/Telegram/desktop."""

    def deliver(self, alert: "Alert", quote: Quote) -> str:
        print(
            f"[ALERT] {alert.symbol} {alert.condition} {alert.target_price}: "
            f"now {quote.price}"
        )
        return "log"


@dataclass
class Alert:
    id: Optional[int]
    symbol: str
    market: str
    condition: str
    target_price: float
    note: Optional[str] = None
    status: str = "active"
    created_at: Optional[str] = None
    triggered_at: Optional[str] = None
    last_checked_price: Optional[float] = None


class AlertRepository:
    def __init__(
        self,
        db_path: Union[str, Path] = DEFAULT_DB_PATH,
        notifier: Optional[Notifier] = None,
    ):
        self.db_path = Path(db_path)
        ensure_tables(self.db_path)
        self.notifier = notifier or LogNotifier()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.db_path))
        con.row_factory = sqlite3.Row
        return con

    def create(
        self,
        symbol: str,
        condition: str,
        target_price: float,
        market: str = "stock",
        note: Optional[str] = None,
    ) -> Alert:
        if condition not in VALID_CONDITIONS:
            raise ValueError("condition must be 'above' or 'below'")
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO price_alerts (symbol, market, condition, target_price, note) "
                "VALUES (?, ?, ?, ?, ?)",
                (symbol.strip().upper(), market, condition, float(target_price), note),
            )
            alert_id = cur.lastrowid
        return self.get(alert_id)  # type: ignore[arg-type]

    def get(self, alert_id: int) -> Optional[Alert]:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM price_alerts WHERE id = ?", (alert_id,)
            ).fetchone()
        return Alert(**dict(row)) if row else None

    def list(self, status: Optional[str] = None) -> List[Alert]:
        query = "SELECT * FROM price_alerts"
        params: tuple = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY created_at DESC"
        with self._connect() as con:
            rows = con.execute(query, params).fetchall()
        return [Alert(**dict(r)) for r in rows]

    def set_status(self, alert_id: int, status: str) -> bool:
        if status not in VALID_STATUSES:
            raise ValueError(f"bad status: {status!r}")
        with self._connect() as con:
            cur = con.execute(
                "UPDATE price_alerts SET status = ? WHERE id = ?", (status, alert_id)
            )
            return cur.rowcount > 0

    def delete(self, alert_id: int) -> bool:
        with self._connect() as con:
            cur = con.execute("DELETE FROM price_alerts WHERE id = ?", (alert_id,))
            return cur.rowcount > 0

    def list_events(self, limit: int = 20) -> List[dict]:
        """Most recent fired-alert events (newest first)."""
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM alert_events ORDER BY fired_at DESC, id DESC "
                "LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def evaluate(self, provider) -> List[dict]:
        """Check every active alert against live quotes. Returns fired events.

        Network/API errors on one symbol never abort the sweep; they are
        reported as error entries in the result list.
        """
        fired: List[dict] = []
        now = datetime.now(timezone.utc).isoformat()
        for alert in self.list(status="active"):
            try:
                quote = provider.get_quote(alert.symbol)
            except Exception as exc:
                fired.append(
                    {"alert_id": alert.id, "symbol": alert.symbol, "error": str(exc)}
                )
                continue
            if quote.price is None:
                continue
            if evaluate_rule(quote.price, alert.condition, alert.target_price):
                with self._connect() as con:
                    con.execute(
                        "INSERT INTO alert_events "
                        "(alert_id, symbol, price, target_price, condition) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (
                            alert.id,
                            alert.symbol,
                            quote.price,
                            alert.target_price,
                            alert.condition,
                        ),
                    )
                    con.execute(
                        "UPDATE price_alerts SET status = 'triggered', "
                        "triggered_at = ?, last_checked_price = ? WHERE id = ?",
                        (now, quote.price, alert.id),
                    )
                self.notifier.deliver(alert, quote)
                fired.append(
                    {
                        "alert_id": alert.id,
                        "symbol": alert.symbol,
                        "price": quote.price,
                        "condition": alert.condition,
                    }
                )
            else:
                with self._connect() as con:
                    con.execute(
                        "UPDATE price_alerts SET last_checked_price = ? WHERE id = ?",
                        (quote.price, alert.id),
                    )
        return fired
