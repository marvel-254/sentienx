"""Stdlib unittest suite for the openstock foundation (pytest-compatible).

Run from the SENTIENX root:
    python3 -m unittest discover -s openstock/tests -v
"""

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # SENTIENX root

from openstock import alerts, market_clock, migrations, palette, quotes, watchlist  # noqa: E402


class MigrationsTest(unittest.TestCase):
    def test_creates_tables_idempotently(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.db"
            tables = migrations.ensure_tables(db)
            self.assertIn("watchlist", tables)
            self.assertIn("price_alerts", tables)
            self.assertIn("alert_events", tables)
            tables_again = migrations.ensure_tables(db)
            self.assertEqual(tables, tables_again)


class WatchlistTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = watchlist.WatchlistRepository(Path(self._tmp.name) / "t.db")

    def tearDown(self):
        self._tmp.cleanup()

    def test_add_list_remove(self):
        self.assertTrue(self.repo.add("AAPL", "stock", "Apple"))
        self.assertFalse(self.repo.add("aapl", "stock"))  # dedup, case-insensitive
        self.assertTrue(self.repo.has("AAPL"))
        self.assertEqual(len(self.repo.list()), 1)
        self.assertTrue(self.repo.remove("AAPL"))
        self.assertFalse(self.repo.has("AAPL"))

    def test_market_filter(self):
        self.repo.add("AAPL", "stock")
        self.repo.add("R_100", "deriv")
        self.assertEqual(len(self.repo.list(market="deriv")), 1)
        self.assertEqual(len(self.repo.list(market="stock")), 1)


class AlertRuleTest(unittest.TestCase):
    def test_above_below(self):
        self.assertTrue(alerts.evaluate_rule(105.0, "above", 100.0))
        self.assertFalse(alerts.evaluate_rule(95.0, "above", 100.0))
        self.assertTrue(alerts.evaluate_rule(95.0, "below", 100.0))
        self.assertFalse(alerts.evaluate_rule(105.0, "below", 100.0))
        with self.assertRaises(ValueError):
            alerts.evaluate_rule(100.0, "cross", 100.0)


class FakeProvider:
    """Deterministic provider for evaluation tests (no network)."""

    def __init__(self, prices):
        self.prices = prices

    def get_quote(self, symbol):
        price = self.prices[symbol]
        return quotes.Quote(
            symbol=symbol,
            market="stock",
            price=price,
            change=None,
            change_percent=None,
            source="fake",
            stale=False,
        )


class AlertEvaluateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = alerts.AlertRepository(Path(self._tmp.name) / "t.db")

    def tearDown(self):
        self._tmp.cleanup()

    def test_fires_and_records_event(self):
        created = self.repo.create("AAPL", "above", 100.0)
        fired = self.repo.evaluate(FakeProvider({"AAPL": 101.5}))
        self.assertEqual(len(fired), 1)
        self.assertEqual(self.repo.get(created.id).status, "triggered")
        self.assertIsNotNone(self.repo.get(created.id).triggered_at)

    def test_no_fire_keeps_active_and_records_price(self):
        created = self.repo.create("AAPL", "above", 100.0)
        self.repo.evaluate(FakeProvider({"AAPL": 99.0}))
        current = self.repo.get(created.id)
        self.assertEqual(current.status, "active")
        self.assertEqual(current.last_checked_price, 99.0)

    def test_provider_error_does_not_abort_sweep(self):
        self.repo.create("AAPL", "above", 100.0)
        self.repo.create("MSFT", "below", 50.0)

        class FlakyProvider(FakeProvider):
            def get_quote(self, symbol):
                if symbol == "AAPL":
                    raise RuntimeError("network down")
                return super().get_quote(symbol)

        fired = self.repo.evaluate(FlakyProvider({"MSFT": 49.0}))
        statuses = {a.symbol: a.status for a in self.repo.list()}
        self.assertEqual(statuses["AAPL"], "active")   # error swallowed
        self.assertEqual(statuses["MSFT"], "triggered")
        self.assertEqual(len([f for f in fired if "error" in f]), 1)


class MarketClockTest(unittest.TestCase):
    def test_deriv_always_open(self):
        self.assertTrue(market_clock.is_market_open("DERIV"))

    def test_nyse_weekend_closed(self):
        saturday = datetime(2026, 10, 17, 12, 0)
        self.assertFalse(market_clock.is_market_open("NYSE", at=saturday))

    def test_nyse_weekday_open(self):
        wednesday_10am = datetime(2026, 10, 14, 10, 0)
        self.assertTrue(market_clock.is_market_open("NYSE", at=wednesday_10am))

    def test_nyse_pre_market_closed(self):
        wednesday_7am = datetime(2026, 10, 14, 7, 0)
        self.assertFalse(market_clock.is_market_open("NYSE", at=wednesday_7am))

    def test_status_line(self):
        line = market_clock.market_status_line("DERIV")
        self.assertIn("OPEN", line)


class PaletteTest(unittest.TestCase):
    def test_search_ranks_and_runs(self):
        reg = palette.ActionRegistry()
        hits = []
        reg.register(
            palette.Action("a", "Add AAPL to watchlist", ("watchlist", "aapl"),
                           lambda: hits.append("a"))
        )
        reg.register(
            palette.Action("b", "Show heatmap", ("heatmap", "market"),
                           lambda: hits.append("b"))
        )
        self.assertEqual(reg.search("heat")[0].id, "b")
        self.assertTrue(reg.run("a"))
        self.assertEqual(hits, ["a"])
        self.assertFalse(reg.run("missing"))

    def test_empty_query_returns_all(self):
        reg = palette.ActionRegistry()
        reg.register(palette.Action("a", "A", (), lambda: None))
        reg.register(palette.Action("b", "B", (), lambda: None))
        self.assertEqual(len(reg.search("")), 2)


class QuoteModelTest(unittest.TestCase):
    def test_direction(self):
        up = quotes.Quote("AAPL", "stock", 101.0, 1.0, 1.0)
        down = quotes.Quote("AAPL", "stock", 99.0, -1.0, -1.0)
        flat = quotes.Quote("AAPL", "stock", 100.0, 0.0, 0.0)
        self.assertEqual(up.direction, "up")
        self.assertEqual(down.direction, "down")
        self.assertEqual(flat.direction, "flat")

    def test_finnhub_requires_key(self):
        import os

        saved = os.environ.pop("FINNHUB_API_KEY", None)
        try:
            with self.assertRaises(ValueError):
                quotes.FinnhubProvider()
        finally:
            if saved is not None:
                os.environ["FINNHUB_API_KEY"] = saved


if __name__ == "__main__":
    unittest.main()
