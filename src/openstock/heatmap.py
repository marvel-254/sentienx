"""Market heatmap (port of OpenStock's dashboard heatmap) for Streamlit.

Builds a treemap from live quotes, colored by percent change. Plotly is
optional at import time, matching the existing dashboard's HAS_PLOTLY
pattern.
"""

from __future__ import annotations

from typing import Callable, Iterable, List, Optional

from .quotes import Quote

try:
    import plotly.express as px  # type: ignore
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False


def build_heatmap_rows(
    quotes: Iterable[Quote],
    sector_of: Optional[Callable[[str], str]] = None,
) -> List[dict]:
    """Flatten quotes into treemap rows. sector_of(symbol) groups tiles."""
    rows: List[dict] = []
    for q in quotes:
        if q.price is None:
            continue
        rows.append(
            {
                "symbol": q.symbol,
                "market": q.market,
                "sector": sector_of(q.symbol) if sector_of else q.market,
                "price": q.price,
                "change_percent": q.change_percent or 0.0,
            }
        )
    return rows


def render_streamlit(rows: List[dict], height: int = 480) -> bool:
    """Render the heatmap inside a Streamlit app. Returns True on success."""
    import streamlit as st

    if not HAS_PLOTLY:
        st.warning("plotly is not installed in this venv; heatmap unavailable.")
        return False
    if not rows:
        st.info("No quote data available for the heatmap yet.")
        return False

    import pandas as pd

    df = pd.DataFrame(rows)
    fig = px.treemap(
        df,
        path=["sector", "symbol"],
        values="price",
        color="change_percent",
        color_continuous_scale=["#ef4444", "#1f2937", "#22c55e"],
        color_continuous_midpoint=0,
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=height,
        paper_bgcolor="#0a0e27",
    )
    st.plotly_chart(fig, use_container_width=True)
    return True
