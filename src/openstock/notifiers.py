"""Alert delivery channels.

v1 decision (sir, 2026-10-13): desktop notifications. DesktopNotifier shells
out to ``notify-send`` (Linux) or ``osascript`` (macOS); when neither exists
it reports ``desktop-unavailable`` instead of raising, so the dashboard can
keep going. The in-app st.toast in the alerts tab is the always-visible
companion channel.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import List, Protocol, Tuple

from .alerts import Alert, LogNotifier
from .quotes import Quote


def build_message(alert: Alert, quote: Quote) -> Tuple[str, str]:
    """(title, body) for an alert notification. Pure function, unit-tested."""
    arrow = "▲" if alert.condition == "above" else "▼"
    title = f"SENTIENX {alert.symbol} {arrow} {alert.target_price:g}"
    body = (
        f"{alert.symbol} is now {quote.price:g} "
        f"({alert.condition} {alert.target_price:g})"
    )
    return title, body


class DesktopNotifier:
    """Desktop notification via notify-send (Linux) or osascript (macOS)."""

    def __init__(self, binary: str = ""):
        if binary:
            self.binary = binary
        elif shutil.which("notify-send"):
            self.binary = "notify-send"
        elif shutil.which("osascript"):
            self.binary = "osascript"
        else:
            self.binary = ""

    @property
    def available(self) -> bool:
        return bool(self.binary)

    def deliver(self, alert: Alert, quote: Quote) -> str:
        if not self.available:
            return "desktop-unavailable"
        title, body = build_message(alert, quote)
        body = body.replace('"', "'")
        title = title.replace('"', "'")
        try:
            if self.binary == "osascript":
                script = f'display notification "{body}" with title "{title}"'
                subprocess.run(
                    ["osascript", "-e", script],
                    timeout=5, check=False, capture_output=True,
                )
            else:
                subprocess.run(
                    [self.binary, title, body],
                    timeout=5, check=False, capture_output=True,
                )
        except Exception:
            return "desktop-failed"
        return "desktop"


class CompositeNotifier:
    """Deliver through every channel; returns comma-joined results."""

    def __init__(self, notifiers: List):
        self.notifiers = list(notifiers)

    def deliver(self, alert: Alert, quote: Quote) -> str:
        return ",".join(n.deliver(alert, quote) for n in self.notifiers)


def make_notifier():
    """Default dashboard notifier: desktop ping + server log line."""
    return CompositeNotifier([DesktopNotifier(), LogNotifier()])
