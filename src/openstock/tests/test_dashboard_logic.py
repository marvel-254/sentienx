"""Tests for the dashboard-facing openstock logic (stdlib-only)."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/

from openstock.alerts import Alert  # noqa: E402
from openstock.demo import (  # noqa: E402
    DEFAULT_SYMBOLS,
    DemoProvider,
    current_bucket,
    demo_price,
)
from openstock.heatmap import build_heatmap_rows, heat_color  # noqa: E402
from openstock.migrations import ensure_tables  # noqa: E402
from openstock.notifiers import (  # noqa: E402
    CompositeNotifier,
    DesktopNotifier,
    build_message,
)
from openstock.quotes import Quote  # noqa: E402
from openstock.streamlit_pages import filter_universe, symbol_universe  # noqa: E402


def _quote(price=100.0, symbol="AAPL", market="stock", change_percent=1.0):
    return Quote(
        symbol=symbol, market=market, price=price, change=1.0,
        change_percent=change_percent, source="test", stale=False,
    )


def _alert(**kw):
    defaults = dict(
        id=1, symbol="AAPL", market="stock", condition="above",
        target_price=100.0,
    )
    defaults.update(kw)
    return Alert(**defaults)


class DemoProviderTests(unittest.TestCase):
    def test_demo_price_deterministic(self):
        self.assertEqual(demo_price("AAPL", 1000), demo_price("AAPL", 1000))

    def test_demo_price_differs_per_symbol(self):
        self.assertNotEqual(demo_price("AAPL", 1000), demo_price("MSFT", 1000))

    def test_quote_fields(self):
        q = DemoProvider().get_quote("r_100")
        self.assertEqual(q.market, "deriv")
        self.assertEqual(q.source, "demo")
        self.assertIsNotNone(q.price)
        self.assertGreater(q.price, 0)
        self.assertLess(abs(q.change_percent), 10.0)
        self.assertGreater(q.high, q.low)

    def test_stock_market_for_unknown_symbol(self):
        q = DemoProvider().get_quote("ZZZZ")
        self.assertEqual(q.market, "stock")

    def test_search_filters(self):
        hits = DemoProvider().search("R_")
        self.assertTrue(hits)
        self.assertTrue(all(h["market"] == "deriv" for h in hits))

    def test_current_bucket_monotonic(self):
        self.assertLessEqual(current_bucket(1000.0), current_bucket(2000.0))


class HeatmapTests(unittest.TestCase):
    def test_neutral_at_zero(self):
        self.assertEqual(heat_color(0.0), "#1f2937")

    def test_clamps_beyond_scale(self):
        self.assertEqual(heat_color(5.0), heat_color(3.0))
        self.assertEqual(heat_color(-9.0), heat_color(-3.0))

    def test_green_and_red_direction(self):
        up = heat_color(2.0)
        down = heat_color(-2.0)
        # Up tiles are greener and less red than down tiles.
        self.assertGreater(int(up[3:5], 16), int(down[3:5], 16))
        self.assertLess(int(up[1:3], 16), int(down[1:3], 16))

    def test_build_rows_skips_missing_price(self):
        rows = build_heatmap_rows([_quote(10.0), _quote(None, symbol="BAD")])
        self.assertEqual([r["symbol"] for r in rows], ["AAPL"])


class NotifierTests(unittest.TestCase):
    def test_build_message_contents(self):
        title, body = build_message(_alert(target_price=105.0), _quote(110.0))
        self.assertIn("AAPL", title)
        self.assertIn("105", title)
        self.assertIn("110", body)

    def test_desktop_unavailable(self):
        from unittest.mock import patch
        with patch("openstock.notifiers.shutil.which", return_value=None):
            notifier = DesktopNotifier()
        self.assertFalse(notifier.available)
        result = notifier.deliver(_alert(), _quote())
        self.assertEqual(result, "desktop-unavailable")

    def test_desktop_failed_on_bad_binary(self):
        notifier = DesktopNotifier(binary="definitely-not-a-real-binary-xyz")
        self.assertTrue(notifier.available)
        self.assertEqual(notifier.deliver(_alert(), _quote()), "desktop-failed")

    def test_composite_joins_results(self):
        class Fake:
            def __init__(self, tag):
                self.tag = tag
                self.calls = []

            def deliver(self, alert, quote):
                self.calls.append(alert.symbol)
                return self.tag

        a, b = Fake("x"), Fake("y")
        result = CompositeNotifier([a, b]).deliver(_alert(), _quote())
        self.assertEqual(result, "x,y")
        self.assertEqual(a.calls, ["AAPL"])


class UniverseTests(unittest.TestCase):
    def test_filter_prefix_priority(self):
        universe = [("AAPL", "stock"), ("AMD", "stock"), ("R_100", "deriv")]
        self.assertEqual(filter_universe(universe, "AA"), [("AAPL", "stock")])
        self.assertEqual(filter_universe(universe, "A")[0], ("AAPL", "stock"))
        self.assertIn(("AMD", "stock"), filter_universe(universe, "A"))

    def test_filter_empty_query_returns_head(self):
        universe = [("AAPL", "stock"), ("AMD", "stock")]
        self.assertEqual(filter_universe(universe, ""), universe)

    def test_filter_limit(self):
        universe = [(f"S{i}", "stock") for i in range(20)]
        self.assertEqual(len(filter_universe(universe, "S", limit=5)), 5)

    def test_symbol_universe_defaults_with_tmp_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            universe = symbol_universe(db_path=Path(tmp) / "t.db")
            pairs = set(universe)
            self.assertIn(("AAPL", "stock"), pairs)
            self.assertIn(("R_100", "deriv"), pairs)
            self.assertLessEqual(len(universe), 40)
            self.assertEqual(len(DEFAULT_SYMBOLS) > 0, True)


class MigrationTests(unittest.TestCase):
    def test_ensure_tables_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.db"
            first = ensure_tables(db)
            second = ensure_tables(db)
            self.assertEqual(first, second)
            for table in ("watchlist", "price_alerts", "alert_events"):
                self.assertIn(table, second)


if __name__ == "__main__":
    unittest.main()
