"""Price alerts (port of OpenStock's alert model + alert actions).

OpenStock evaluates alerts server-side on an Inngest cron. SENTIENX is
single-user and local, so evaluation is a plain function the dashboard
or a background thread can call on a timer (Phase 2).

Uses core.db_adapter: PostgreSQL when DATABASE_URL is set, SQLite
locally. Tests may pass an explicit db_path to pin SQLite.

Pure rule logic lives in evaluate_rule() so it is trivially testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Protocol, Union

from .migrations import DEFAULT_DB_PATH, ensure_tables
from .quotes import Quote

try:
    from core.db_adapter import DatabaseAdapter, get_adapter
except ImportError:
    from core.db_adapter import DatabaseAdapter, get_adapter

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
        db_path: Optional[Union[str, Path]] = None,
        notifier: Optional[Notifier] = None,
    ):
        if db_path is None:
            self.adapter = get_adapter()
        else:
            self.adapter = DatabaseAdapter(sqlite_path=db_path)
        ensure_tables(db_path)
        self.notifier = notifier or LogNotifier()

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
        alert_id = self.adapter.insert(
            "INSERT INTO price_alerts (symbol, market, condition, target_price, note) "
            "VALUES (?, ?, ?, ?, ?)",
            (symbol.strip().upper(), market, condition, float(target_price), note),
        )
        if alert_id is not None:
            return self.get(alert_id)  # type: ignore[arg-type]
        # RETURNING id failed unexpectedly: fall back to newest row
        row = self.adapter.fetchone(
            "SELECT id FROM price_alerts WHERE symbol = ? ORDER BY id DESC LIMIT 1",
            (symbol.strip().upper(),),
        )
        return self.get(row["id"]) if row else None  # type: ignore

    def get(self, alert_id: int) -> Optional[Alert]:
        row = self.adapter.fetchone(
            "SELECT * FROM price_alerts WHERE id = ?", (alert_id,)
        )
        return Alert(**row) if row else None

    def list(self, status: Optional[str] = None) -> List[Alert]:
        query = "SELECT * FROM price_alerts"
        params: tuple = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY created_at DESC"
        return [Alert(**r) for r in self.adapter.fetchall(query, params)]

    def set_status(self, alert_id: int, status: str) -> bool:
        if status not in VALID_STATUSES:
            raise ValueError(f"bad status: {status!r}")
        return bool(self.adapter.execute(
            "UPDATE price_alerts SET status = ? WHERE id = ?", (status, alert_id)
        ))

    def delete(self, alert_id: int) -> bool:
        return bool(self.adapter.execute(
            "DELETE FROM price_alerts WHERE id = ?", (alert_id,)
        ))

    def list_events(self, limit: int = 20) -> List[dict]:
        """Most recent fired-alert events (newest first)."""
        return self.adapter.fetchall(
            "SELECT * FROM alert_events ORDER BY fired_at DESC, id DESC LIMIT ?",
            (limit,),
        )

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
                self.adapter.insert(
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
                self.adapter.execute(
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
                self.adapter.execute(
                    "UPDATE price_alerts SET last_checked_price = ? WHERE id = ?",
                    (quote.price, alert.id),
                )
        return fired
