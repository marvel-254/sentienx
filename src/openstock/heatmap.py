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
    """Render the heatmap inside a Streamlit app. Returns True on success.

    Falls back to a dependency-free HTML/CSS grid when plotly is missing
    (the SENTIENX venv has neither plotly nor altair by policy).
    """
    import streamlit as st

    if not HAS_PLOTLY:
        render_streamlit_html(rows)
        return True
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


# ---------------------------------------------------------------------------
# dependency-free HTML/CSS fallback (no plotly, no altair needed)
# ---------------------------------------------------------------------------

NEUTRAL_RGB = (31, 41, 55)    # #1f2937
UP_RGB = (34, 197, 94)        # #22c55e
DOWN_RGB = (239, 68, 68)      # #ef4444


def _lerp_color(a: tuple, b: tuple, t: float) -> str:
    channel = lambda i: int(round(a[i] + (b[i] - a[i]) * t))  # noqa: E731
    return "#{:02x}{:02x}{:02x}".format(*(channel(i) for i in range(3)))


def heat_color(change_percent: float, max_abs: float = 3.0) -> str:
    """Green->neutral->red hex for a % change, clamped to +/- max_abs."""
    t = max(-1.0, min(1.0, (change_percent or 0.0) / max_abs))
    if t >= 0:
        return _lerp_color(NEUTRAL_RGB, UP_RGB, t)
    return _lerp_color(NEUTRAL_RGB, DOWN_RGB, -t)


def render_streamlit_html(rows: List[dict]) -> None:
    """CSS-grid heatmap of tiles colored by % change (no chart libs)."""
    import html as _html
    import streamlit as st

    if not rows:
        st.info("No quote data available for the heatmap yet.")
        return
    tiles = []
    for r in sorted(rows, key=lambda item: -abs(item["change_percent"])):
        color = heat_color(r["change_percent"])
        pct = r["change_percent"]
        sign = "+" if pct >= 0 else ""
        tiles.append(
            f'<div style="background:{color};color:#0b1020;'
            f'border-radius:10px;padding:10px 12px;min-height:64px">'
            f'<div style="font-weight:700;font-size:0.95rem">'
            f'{_html.escape(str(r["symbol"]))}</div>'
            f'<div style="font-size:0.8rem;opacity:.85">{r["price"]:g}</div>'
            f'<div style="font-size:0.85rem;font-weight:700">'
            f'{sign}{pct:.2f}%</div></div>'
        )
    grid = (
        '<div style="display:grid;'
        'grid-template-columns:repeat(auto-fill,minmax(130px,1fr));'
        f'gap:8px">{"".join(tiles)}</div>'
    )
    st.markdown(grid, unsafe_allow_html=True)
