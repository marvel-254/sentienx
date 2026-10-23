"""TradingView widget embeds (port of OpenStock's TradingViewWidget.tsx).

OpenStock renders TradingView's embeddable widgets in React; Streamlit
renders the same widgets through components.v1.html. No API key needed.
"""

from __future__ import annotations

import json
from typing import List

WIDGETS = (
    "advanced-chart",
    "technical-analysis",
    "symbol-info",
    "symbol-profile",
    "financials",
    "ticker-tape",
    "market-overview",
    "hotlists",
    "timeline",
)


def widget_html(
    symbol: str,
    widget: str = "advanced-chart",
    theme: str = "dark",
    height: int = 420,
    interval: str = "D",
) -> str:
    if widget not in WIDGETS:
        raise ValueError(f"widget must be one of {WIDGETS}")
    config = {
        "interval": interval,
        "width": "100%",
        "height": height,
        "isTransparent": True,
        "hide_side_toolbar": True,
        "theme": theme,
        "style": "1",
        "locale": "en",
        "symbol": symbol,
    }
    container_id = f"tv_{widget}_{abs(hash(symbol)) % 10**8}"
    return (
        f'<div class="tradingview-widget-container" style="height:{height}px">'
        f'<div id="{container_id}"></div>'
        f"</div>"
        f'<script src="https://s3.tradingview.com/external-embedding/'
        f'embed-widget-{widget}.js" async>'
        f"{json.dumps(config)}"
        f"</script>"
    )


def render_streamlit(
    symbol: str,
    widget: str = "advanced-chart",
    height: int = 420,
    theme: str = "dark",
):
    import streamlit.components.v1 as components

    return components.html(
        widget_html(symbol, widget, theme=theme, height=height),
        height=height + 16,
    )
