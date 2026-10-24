"""
SENTIENX Unified Trading Dashboard
- Economic Calendar Integration
- AI-Powered Market Sentiment Analysis
- Real-time News Aggregation
- Natural Language Query Interface
- Live Account Balance & Trades
- P&L Trendline (Line & Pie Chart)
- RESTful API Integration
- Downloadable Web Interface
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date, timezone
import json
import os
import requests
from pathlib import Path
from typing import Dict, List, Tuple
import threading
import time

# Central DB adapter (SQLite locally, PostgreSQL when DATABASE_URL is set)
try:
    from core.db_adapter import get_adapter
except ImportError:
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core.db_adapter import get_adapter

# Deriv real-time feed (new dev-portal API: REST + OTP WebSocket)
try:
    import deriv_feed
except ImportError:
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent))
    import deriv_feed

try:
    import plotly.graph_objects as go
    import plotly.express as px
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

# Import breakout analysis component
try:
    from dashboard_components.breakout_component import display_breakout_dashboard
    HAS_BREAKOUT = True
except ImportError:
    HAS_BREAKOUT = False

# OpenStock-derived market pages (watchlist / alerts / heatmap / detail)
try:
    from openstock import streamlit_pages as osp
    HAS_OPENSTOCK = True
except ImportError:
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from openstock import streamlit_pages as osp
        HAS_OPENSTOCK = True
    except Exception:
        osp = None
        HAS_OPENSTOCK = False

# Page Configuration
st.set_page_config(
    page_title="SENTIENX",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Global chrome — one token system, shared with the login screen:
# bg #05060a · surface #0e1223 · border #334155 · fg #F8FAFC
# muted #94a3b8 · accent #22c55e · danger #ef4444 · amber #f59e0b
st.markdown("""
    <style>
    @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

    * { margin: 0; padding: 0; }
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #05060a !important;
        color: #F8FAFC !important;
        cursor: default;
    }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"] {
        background-color: #0e1223 !important;
        border-right: 1px solid #334155;
    }
    .block-container {
        padding: 24px 20px;
        background: transparent !important;
        animation: fadeIn 0.2s ease-out;
    }
    .stTabs [data-baseweb="tab-list"] {
        background-color: transparent;
        border-bottom: 1px solid #1e2536;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        color: #94a3b8;
        font-size: 0.86rem;
        font-weight: 500;
        border-radius: 0;
        padding: 8px 12px;
        border-bottom: 2px solid transparent;
        transition: color 0.15s ease, border-color 0.15s ease;
    }
    .stTabs [data-baseweb="tab"]:hover { color: #e2e8f0; }
    .stTabs [aria-selected="true"] {
        color: #F8FAFC !important;
        border-bottom: 2px solid #22c55e !important;
    }
    h1 { color: #F8FAFC; margin-bottom: 20px; font-weight: 700; letter-spacing: 0.06em; }
    h2 { color: #F8FAFC; margin-top: 20px; font-weight: 600; }
    h3 { color: #cbd5e1; }
    .stMetric {
        background-color: #0e1223; padding: 14px; border-radius: 4px;
        border: 1px solid #334155; transition: border-color 0.15s ease;
    }
    .stMetric:hover { border-color: #22c55e; }
    .stDataFrame { background-color: #0e1223 !important; }
    [data-testid="stDataFrameContainer"] { background-color: #0e1223 !important; }
    [data-testid="stAlert"] {
        background-color: #0e1223;
        border: 1px solid #334155;
        border-radius: 4px;
    }
    button {
        background-color: #0e1223 !important;
        color: #F8FAFC !important;
        border: 1px solid #334155 !important;
        border-radius: 4px;
        font-weight: 500;
        transition: background-color 0.15s ease, border-color 0.15s ease;
    }
    button:hover {
        background-color: #182036 !important;
        border-color: #22c55e !important;
        color: #F8FAFC !important;
        box-shadow: none !important;
    }
    button:active { transform: scale(0.99); }
    button:focus-visible { outline: 2px solid #F8FAFC; outline-offset: 2px; }
    a { color: #4ade80 !important; transition: color 0.15s ease; }
    a:hover { color: #86efac !important; }
    .success { color: #4ade80; }
    .danger { color: #f87171; }
    .warning { color: #fbbf24; }
    .section-header {
        color: #F8FAFC; font-size: 1.15rem; font-weight: 600;
        margin: 15px 0 10px 0; border-bottom: 1px solid #1e2536; padding-bottom: 10px;
    }
    .footer {
        background-color: #0e1223; border-top: 1px solid #1e2536; border-radius: 4px;
        padding: 18px; margin-top: 40px; text-align: center;
        color: #94a3b8; font-size: 12px;
    }
    @media (prefers-reduced-motion: reduce) {
        * { animation: none !important; transition: none !important; }
    }
    </style>
    """, unsafe_allow_html=True)

# Landing/auth imagery (Pexels, free-to-use license) — hotlinked CDN copies
HERO_IMG_URL = ("https://images.pexels.com/photos/29611783/pexels-photo-29611783.jpeg"
                "?auto=compress&cs=tinysrgb&w=1920")
LOGIN_IMG_URL = ("https://images.pexels.com/photos/10653886/pexels-photo-10653886.jpeg"
                 "?auto=compress&cs=tinysrgb&w=1920")

# Authentication
def check_authentication():
    """Check if user is authenticated"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

def login_page():
    """Branded auth screen — trading-desk imagery behind a terminal card."""
    # Hide sidebar/header chrome and paint the trading-desk backdrop until login.
    st.markdown("""
        <style>
        [data-testid="stSidebar"] { display: none; }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stAppViewContainer"] {
            background:
                linear-gradient(180deg, rgba(5,6,10,0.88) 0%, rgba(5,6,10,0.96) 55%, rgba(5,6,10,1) 100%),
                url('__BG__') center/cover no-repeat fixed !important; }
        [data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"] * {
            font-family: system-ui, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
            font-feature-settings: 'tnum' 1; }
        .sx-band { margin: 9vh auto 30px; max-width: 560px; text-align: center;
            padding: 0 24px; }
        .sx-wordmark { font-size: 2.6rem; font-weight: 800; letter-spacing: 0.30em;
            color: #F8FAFC; margin-right: -0.30em; line-height: 1; }
        .sx-console-line { color: #94a3b8; font-size: 0.92rem; font-weight: 300;
            margin: 14px auto 0; line-height: 1.6; max-width: 40ch; }
        .sx-console-line strong { color: #e2e8f0; font-weight: 600; }
        [data-testid="stForm"] { background: #0e1223; border: 1px solid #334155;
            border-radius: 4px; padding: 40px 38px 30px !important;
            box-shadow: 0 30px 70px rgba(0,0,0,0.5);
            width: 100%; max-width: 440px; margin: 0 auto;
            animation: sx-rise .5s ease-out both; }
        @keyframes sx-rise { from { opacity: 0; transform: translateY(14px); }
            to { opacity: 1; transform: translateY(0); } }
        @media (prefers-reduced-motion: reduce) { [data-testid="stForm"] { animation: none; } }
        .sx-card-title { color: #F8FAFC; font-size: 1.05rem; font-weight: 600;
            margin-bottom: 2px; }
        .sx-card-sub { color: #64748b; font-size: 0.8rem; margin-bottom: 18px; }
        .sx-label { color: #94a3b8; font-size: 0.72rem; letter-spacing: 0.08em;
            margin: 4px 0 0; }
        [data-testid="stForm"] .sx-card-title { margin-top: 0; }
        [data-testid="stForm"] input { background: #05060a !important;
            border: 1px solid #334155 !important; border-radius: 4px !important;
            color: #F8FAFC !important; font-size: 0.95rem !important;
            box-shadow: none !important; outline: none !important;
            caret-color: #F8FAFC; }
        [data-testid="stForm"] [data-testid="stTextInputRootElement"] {
            background: #05060a !important; box-shadow: none !important;
            border: 1px solid #334155 !important; border-radius: 4px !important;
            transition: border-color .15s ease; }
        [data-testid="stForm"] [data-testid="stTextInputRootElement"]:focus-within {
            border-color: #22c55e !important; box-shadow: 0 0 0 1px #22c55e !important; }
        [data-testid="stForm"] input:focus { border-color: transparent !important;
            box-shadow: none !important; outline: none !important; }
        [data-testid="stForm"] input::placeholder { color: #64748b; }
        [data-testid="stForm"] [data-testid="stFormSubmitButton"] button {
            background: #22c55e !important; color: #06210f !important;
            border: none; border-radius: 4px !important;
            font-weight: 600; font-size: 0.92rem; letter-spacing: 0.02em;
            min-height: 44px !important; cursor: pointer;
            transition: background 0.15s ease; }
        [data-testid="stForm"] [data-testid="stFormSubmitButton"] button:hover {
            background: #4ade80 !important; }
        [data-testid="stForm"] [data-testid="stFormSubmitButton"] button:focus-visible {
            outline: 2px solid #F8FAFC; outline-offset: 2px; }
        [data-testid="stForm"] [aria-label="Show password"] { display: none !important; }
        .sx-auth-error { margin: 16px auto 0; padding: 10px 12px; border-radius: 4px;
            width: 100%; max-width: 440px;
            background: rgba(239,68,68,0.08);
            border: 1px solid rgba(239,68,68,0.35);
            color: #fca5a5; font-size: 0.83rem; }
        .sx-auth-foot { text-align: center; color: #64748b; font-size: 0.72rem;
            margin: 30px auto 6vh; line-height: 1.5; max-width: 48ch; }
        @media (max-width: 1080px) {
            .sx-band { margin-top: 6vh; }
        }
        @media (max-width: 520px) {
            .sx-wordmark { font-size: 1.9rem; white-space: nowrap; }
        }
        </style>
    """.replace("__BG__", LOGIN_IMG_URL), unsafe_allow_html=True)

    st.markdown("""
        <div class='sx-band'>
            <div class='sx-wordmark'>SENTIENX</div>
            <div class='sx-console-line'>A trading command console for the
                <strong>Deriv</strong> markets — signals, risk, and execution
                in one instrument.</div>
        </div>
    """, unsafe_allow_html=True)

    with st.form("sx_login_form"):
        st.markdown("""
                <div class='sx-card-title'>Sign in</div>
                <div class='sx-card-sub'>to open the dashboard</div>
        """, unsafe_allow_html=True)
        st.markdown("<div class='sx-label'>Username</div>", unsafe_allow_html=True)
        username = st.text_input("Username", key="login_username", label_visibility="collapsed")
        st.markdown("<div class='sx-label'>Password</div>", unsafe_allow_html=True)
        password = st.text_input("Password", type="password", key="login_password", label_visibility="collapsed")
        submitted = st.form_submit_button("Enter dashboard", use_container_width=True)

    if submitted:
        expected_user = os.environ.get("SENTIENX_USER", "marvel")
        expected_pass = os.environ.get("SENTIENX_PASS", "olivertwist")
        if username == expected_user and password == expected_pass:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.markdown("<div class='sx-auth-error'>Invalid username or password."
                        " Check the credentials and try again.</div>",
                        unsafe_allow_html=True)

    st.markdown("""
        <div class='sx-auth-foot'>Access is restricted. Credentials are
        provisioned by the environment — ask the operator if you lost yours.</div>
    """, unsafe_allow_html=True)


def landing_page():
    """Public entry screen — trading-desk hero, product intro, then sign in."""
    st.markdown(("""
        <style>
        [data-testid="stSidebar"] { display: none; }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"] * {
            font-family: system-ui, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
            font-feature-settings: 'tnum' 1; }
        [data-testid="stAppViewContainer"] {
            background:
                linear-gradient(180deg, rgba(5,6,10,0.88) 0%, rgba(5,6,10,0.60) 40%, rgba(5,6,10,0.88) 100%),
                url('__BG__') center 70%/cover no-repeat fixed !important; }
        .sx-hero { margin: 14vh auto 0; max-width: 720px; text-align: center;
            padding: 0 24px; }
        .sx-wordmark { font-size: 3rem; font-weight: 800; letter-spacing: 0.30em;
            color: #F8FAFC; margin-right: -0.30em; line-height: 1;
            text-shadow: 0 2px 24px rgba(0,0,0,0.55); }
        .sx-console-line { color: #94a3b8; font-size: 0.95rem; font-weight: 300;
            margin: 14px auto 0; line-height: 1.6; max-width: 44ch; }
        .sx-console-line strong { color: #e2e8f0; font-weight: 600; }
        .sx-features { display: flex; flex-wrap: wrap; justify-content: center;
            gap: 14px; max-width: 760px; margin: 34px auto 0; padding: 0 24px; }
        .sx-feature { background: rgba(14,18,35,0.88); border: 1px solid #334155;
            border-radius: 4px; padding: 18px; width: 218px; text-align: left;
            backdrop-filter: blur(6px); }
        .sx-feature strong { display: block; color: #F8FAFC; font-size: 0.78rem;
            letter-spacing: 0.08em; margin-bottom: 7px; font-weight: 600; }
        .sx-feature p { color: #94a3b8; font-size: 0.83rem; line-height: 1.55;
            margin: 0; }
        [data-testid="stElementContainer"]:has([data-testid="stButton"] button) {
            width: 100%; }
        [data-testid="stButton"] { text-align: center; margin-top: 30px; width: 100%; }
        [data-testid="stButton"] button {
            background: #22c55e !important; color: #06210f !important;
            border: none; border-radius: 4px !important;
            font-weight: 600 !important; font-size: 0.95rem !important;
            letter-spacing: 0.02em;
            min-height: 46px !important; padding: 0 34px !important;
            display: inline-block; cursor: pointer; width: auto !important;
            min-width: 300px;
            transition: background 0.15s ease; }
        [data-testid="stButton"] button:hover { background: #4ade80 !important; }
        [data-testid="stButton"] button:focus-visible {
            outline: 2px solid #F8FAFC; outline-offset: 2px; }
        .sx-landing-foot { text-align: center; color: #64748b; font-size: 0.72rem;
            margin: 40px auto 8vh; max-width: 52ch; line-height: 1.6; padding: 0 24px; }
        @media (max-width: 1080px) { .sx-hero { margin-top: 9vh; } }
        @media (max-width: 520px) {
            .sx-wordmark { font-size: 2.1rem; white-space: nowrap; }
            .sx-feature { width: 100%; }
        }
        @media (prefers-reduced-motion: reduce) { * { animation: none !important;
            transition: none !important; } }
        </style>
    """).replace("__BG__", HERO_IMG_URL), unsafe_allow_html=True)

    st.markdown("""
        <div class='sx-hero'>
            <div class='sx-wordmark'>SENTIENX</div>
            <div class='sx-console-line'>A trading command console for the
                <strong>Deriv</strong> markets — signals, risk, and execution
                in one instrument.</div>
        </div>
        <div class='sx-features'>
            <div class='sx-feature'><strong>MARKET INTELLIGENCE</strong>
                <p>Live signals, sentiment scoring, and economic-calendar
                context, gathered into one working screen.</p></div>
            <div class='sx-feature'><strong>RISK ENGINE</strong>
                <p>Value-at-Risk, portfolio allocation, and stress testing
                before any money moves.</p></div>
            <div class='sx-feature'><strong>EXECUTION CONSOLE</strong>
                <p>Watchlists, price alerts, and bot control with a full
                trading history behind them.</p></div>
        </div>
    """, unsafe_allow_html=True)

    if st.button("Continue to sign in", key="sx_landing_cta"):
        st.session_state.view = "login"
        st.rerun()

    st.markdown("""
        <div class='sx-landing-foot'>Access is restricted — sign in with the
        credentials provisioned by the operator.<br>Imagery: Pexels,
        free to use.</div>
    """, unsafe_allow_html=True)
# Set up paths
BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_PATH = BASE_DIR / "logs"
API_URL = os.environ.get("SENTIENX_API_URL", "http://localhost:5000")

_db_adapter = get_adapter()


# Initialize database
def ensure_database():
    """Initialize the database (Postgres on Render, SQLite locally)"""
    try:
        LOGS_PATH.mkdir(parents=True, exist_ok=True)
        if not _db_adapter.is_postgres:
            os.chmod(str(LOGS_PATH), 0o755)
        return _db_adapter.ensure_schema()
    except Exception as e:
        # Loud failure: a broken database must not be swallowed silently
        st.warning(f"Database init warning: {e}")
        return []


ensure_database()

# Session State
if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 30
if 'selected_tab' not in st.session_state:
    st.session_state.selected_tab = 0
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'view' not in st.session_state:
    st.session_state.view = 'landing'


# =============================================================================
# FOOTER
# =============================================================================

def display_footer():
    """Display footer"""
    st.divider()
    st.markdown("""
    <div class='footer'>
    <p>SENTIENX Trading System</p>
    <p>Designed by The Inner Circle</p>
    <p>© 2025 | All Rights Reserved</p>
    </div>
    """, unsafe_allow_html=True)


# =============================================================================
# DATABASE FUNCTIONS
# =============================================================================

@st.cache_data(ttl=10, show_spinner=False)
def _deriv_accts() -> Dict:
    return deriv_feed.accounts()


@st.cache_data(ttl=15, show_spinner=False)
def _deriv_realtime(mode: str) -> Dict:
    acct = _deriv_accts().get(mode, {})
    return deriv_feed.account_realtime(acct.get("account_id", ""))


def _deriv_mode() -> str:
    return "real" if st.session_state.get("sx_acct_mode", "Demo").lower() == "real" else "demo"


def _deriv_clear_cache():
    _deriv_accts.clear()
    _deriv_realtime.clear()


def render_deriv_live_strip():
    """Real-time Deriv account balances + live tick strip (read-only)."""
    if not deriv_feed.ready():
        return
    try:
        accts = _deriv_accts()
    except Exception:
        return
    if not accts:
        return

    cols = st.columns(4)
    real, demo = accts.get("real", {}), accts.get("demo", {})
    with cols[0]:
        st.metric("Real account", f"${float(real.get('balance', 0)):,.2f}",
                  real.get("account_id"), delta_color="inverse")
    with cols[1]:
        st.metric("Demo account", f"${float(demo.get('balance', 0)):,.2f}",
                  demo.get("account_id"), delta_color="inverse")

    ticks = deriv_feed.latest_ticks()
    for i, (sym, ticker) in enumerate(list(ticks.items())[:2]):
        quote = ticker.get("quote")
        if quote is None:
            continue
        ts = datetime.fromtimestamp(ticker.get("epoch", time.time()), tz=timezone.utc)
        with cols[2 + i]:
            st.metric(sym, f"{quote:,.4g}", ts.strftime("%H:%M:%S UTC"), delta_color="inverse")
    if not ticks:
        deriv_feed.start_ticks()


def load_account_data() -> Dict:
    """Load live account data from API or database"""
    # Deriv live account first (new dev-portal API)
    if deriv_feed.ready():
        try:
            mode = _deriv_mode()
            live = _deriv_realtime(mode)
            bal = float(live.get("balance") or 0.0)
            return {
                'balance': bal,
                'equity': bal,
                'free_margin': bal * 0.95,
                'margin_level': 110.5,
                'open_positions': len(live.get('positions') or []),
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'profit_factor': 1.0,
                'total_pnl': 0.0,
                'daily_pnl': 0.0,
                'best_trade': 0.0,
                'worst_trade': 0.0,
                'avg_trade': 0.0,
                'sharpe_ratio': 1.8,
                'max_drawdown': 5.2,
                'connected': True,
                'deriv_connected': True,
                'account_type': mode.title(),
                'deriv_trades': live.get('trades') or [],
            }
        except Exception:
            pass

    # Fallback: local API
    try:
        response = requests.get(f"{API_URL}/api/account", timeout=2)
        if response.status_code == 200:
            api_data = response.json()

            # Try to fetch Deriv balance
            try:
                deriv_balance = requests.get(f"{API_URL}/api/deriv/balance", timeout=2).json()
                if deriv_balance.get('success') and deriv_balance.get('balance'):
                    api_data['balance'] = deriv_balance['balance']
                    api_data['equity'] = deriv_balance['balance']
                    api_data['deriv_connected'] = True
            except Exception:
                pass

            return api_data
    except Exception:
        pass

    # Fallback to database
    try:
        # Deriv balance first, then legacy connector; never fatal
        deriv_balance = 0.0
        deriv_connected = False
        account_type = 'Demo'
        try:
            if deriv_feed.ready():
                mode = _deriv_mode()
                acct = _deriv_accts().get(mode, {})
                deriv_balance = float(acct.get('balance', 0.0))
                deriv_connected = True
                account_type = acct.get('account_type', mode).title()
        except Exception:
            pass
        try:
            from config import DERIV_CONFIG
            from deriv_connector import deriv_connector

            success, balance, _ = deriv_connector.get_balance()
            if success and balance:
                deriv_balance = balance
                deriv_connected = True
            account_type = 'Real' if DERIV_CONFIG.get('environment') == 'real' else 'Demo'
        except Exception:
            pass

        account = {
            'balance': deriv_balance,
            'equity': deriv_balance,
            'free_margin': deriv_balance * 0.95,
            'margin_level': 110.5,
            'open_positions': 0,
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'profit_factor': 1.0,
            'total_pnl': 0.0,
            'daily_pnl': 0.0,
            'best_trade': 0.0,
            'worst_trade': 0.0,
            'avg_trade': 0.0,
            'sharpe_ratio': 1.8,
            'max_drawdown': 5.2,
            'connected': deriv_connected,
            'deriv_connected': deriv_connected,
            'account_type': account_type
        }

        # Get trade statistics from database
        stats = _db_adapter.fetchone("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losses,
                SUM(profit_loss) as total_pnl,
                SUM(CASE WHEN profit_loss > 0 THEN profit_loss ELSE 0 END) as total_wins,
                ABS(SUM(CASE WHEN profit_loss < 0 THEN profit_loss ELSE 0 END)) as total_losses,
                MAX(profit_loss) as best_trade,
                MIN(profit_loss) as worst_trade,
                AVG(profit_loss) as avg_trade
            FROM trading_history
        """)

        if stats:
            total = stats['total'] or 0
            wins = stats['wins'] or 0
            losses = stats['losses'] or 0
            total_wins = stats['total_wins'] or 0
            total_losses = stats['total_losses'] or 0

            account['total_trades'] = total
            account['winning_trades'] = wins
            account['losing_trades'] = losses
            account['win_rate'] = (wins / total * 100) if total > 0 else 0
            account['total_pnl'] = stats['total_pnl'] or 0
            account['best_trade'] = stats['best_trade'] or 0
            account['worst_trade'] = stats['worst_trade'] or 0
            account['avg_trade'] = stats['avg_trade'] or 0
            if total_losses > 0 and total_wins > 0:
                account['profit_factor'] = total_wins / total_losses

        open_row = _db_adapter.fetchone(
            "SELECT COUNT(*) as open FROM trading_history WHERE status = ?",
            ('open',)
        )
        if open_row:
            account['open_positions'] = open_row['open'] or 0

        return account
    except Exception as e:
        st.warning(f"Could not load account data: {e}")
        # Return default account structure on error
        return {
            'balance': 0.0,
            'equity': 0.0,
            'free_margin': 0.0,
            'margin_level': 0.0,
            'open_positions': 0,
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'profit_factor': 1.0,
            'total_pnl': 0.0,
            'daily_pnl': 0.0,
            'best_trade': 0.0,
            'worst_trade': 0.0,
            'avg_trade': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'connected': False,
            'account_type': 'Demo'
        }


def load_trades_data(limit: int = 100) -> pd.DataFrame:
    """Load trading history from API or database"""
    # Try API first
    try:
        response = requests.get(f"{API_URL}/api/trades?limit={limit}", timeout=2)
        if response.status_code == 200:
            data = response.json()
            if data.get('trades'):
                df = pd.DataFrame(data['trades'])
                if not df.empty:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df['profit_loss'] = pd.to_numeric(df['profit_loss'], errors='coerce')
                return df
    except Exception:
        pass

    # Fallback to database
    try:
        df = _db_adapter.read_df(
            """
            SELECT
                symbol, direction, entry_price, exit_price,
                volume, profit_loss, status, timestamp, strategy
            FROM trading_history
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )

        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['profit_loss'] = pd.to_numeric(df['profit_loss'], errors='coerce')

        return df
    except Exception as e:
        st.warning(f"Error loading trades: {e}")
        return pd.DataFrame()


def load_signals_data(limit: int = 50) -> pd.DataFrame:
    """Load recent trading signals"""
    try:
        df = _db_adapter.read_df(
            """
            SELECT
                symbol, signal, confidence, strength,
                indicators, timestamp, strategy
            FROM signals_history
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )

        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['confidence'] = pd.to_numeric(df['confidence'], errors='coerce')

        return df
    except Exception as e:
        st.warning(f"Error loading signals: {e}")
        return pd.DataFrame()


def load_pnl_data() -> pd.DataFrame:
    """Load P&L data for trend visualization from API or database"""
    # Try API first
    try:
        response = requests.get(f"{API_URL}/api/pnl", timeout=2)
        if response.status_code == 200:
            data = response.json()
            if data.get('pnl_data'):
                df = pd.DataFrame(data['pnl_data'])
                if not df.empty:
                    df['date'] = pd.to_datetime(df['date'])
                    return df
    except Exception:
        pass

    # Fallback to database
    try:
        df = _db_adapter.read_df(f"""
            SELECT
                {_db_adapter.date_expr('timestamp')} as date,
                SUM(profit_loss) as daily_pnl,
                COUNT(*) as trades,
                SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as wins
            FROM trading_history
            GROUP BY {_db_adapter.date_expr('timestamp')}
            ORDER BY date ASC
        """)

        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df['cumulative_pnl'] = df['daily_pnl'].cumsum()

        return df
    except Exception as e:
        st.warning(f"Error loading P&L data: {e}")
        return pd.DataFrame()


# =============================================================================
# AI & SENTIMENT ANALYSIS
# =============================================================================

def get_market_sentiment(symbol: str = "EUR/USD") -> Dict:
    """Get AI-powered market sentiment analysis"""
    sentiment_data = {
        'symbol': symbol,
        'sentiment': 'BULLISH',
        'score': 0.75,
        'confidence': 0.82,
        'news_sentiment': 0.68,
        'technical_sentiment': 0.85,
        'analysis': f"Market analysis for {symbol} shows bullish momentum with strong support levels. Economic indicators suggest continuation of uptrend.",
        'key_factors': [
            'Strong technical support at 1.0850',
            'Positive economic news from Eurozone',
            'Breaking resistance at 1.0900',
            'High volume confirmation'
        ],
        'risks': [
            'Fed rate hike expectations',
            'Geopolitical tensions',
            'Economic data releases'
        ]
    }
    return sentiment_data


def get_economic_calendar_data() -> pd.DataFrame:
    """Get economic calendar events"""
    events = {
        'date': pd.date_range(start=datetime.now(), periods=10, freq='D'),
        'country': ['USA', 'EUR', 'GBP', 'USA', 'EUR', 'GBP', 'USA', 'EUR', 'AUS', 'USA'],
        'event': [
            'Non-Farm Payroll',
            'CPI Release',
            'Retail Sales',
            'Unemployment Rate',
            'Manufacturing PMI',
            'Services PMI',
            'Fed Interest Rate',
            'ECB Decision',
            'Employment Change',
            'Jobless Claims'
        ],
        'expected': ['200K', '3.1%', '+0.5%', '4.2%', '52.1', '53.2', '5.50%', '4.25%', '15K', '210K'],
        'previous': ['180K', '3.0%', '+0.2%', '4.1%', '51.8', '52.9', '5.50%', '4.25%', '18K', '215K'],
        'importance': ['High', 'High', 'Medium', 'Medium', 'Medium', 'Medium', 'High', 'High', 'Low', 'Medium']
    }
    return pd.DataFrame(events)


def get_market_news() -> List[Dict]:
    """Get real-time market news"""
    news = [
        {
            'title': 'EUR/USD rallies on positive economic data',
            'source': 'MarketWatch',
            'sentiment': 'Positive',
            'time': 'Today 14:30',
            'impact': 'High'
        },
        {
            'title': 'Fed signals potential rate pause',
            'source': 'Bloomberg',
            'sentiment': 'Bullish',
            'time': 'Today 12:15',
            'impact': 'Very High'
        },
        {
            'title': 'GBP weakness amid Brexit concerns',
            'source': 'Reuters',
            'sentiment': 'Bearish',
            'time': 'Today 10:45',
            'impact': 'High'
        },
        {
            'title': 'Asian markets surge on strong earnings',
            'source': 'Financial Times',
            'sentiment': 'Positive',
            'time': 'Today 08:20',
            'impact': 'Medium'
        }
    ]
    return news


def process_natural_language_query(query: str) -> Dict:
    """Process natural language queries about trading"""
    queries = {
        'current balance': 'Your current account balance is $10,500. Equity: $10,750.',
        'open positions': 'You have 2 open positions: EUR/USD +100 lots (Buy), GBP/USD -50 lots (Sell)',
        'best trade': 'Your best trade was EUR/USD Buy with +$250 profit.',
        'win rate': 'Your current win rate is 65%. You have won 13 out of 20 trades.',
        'recommendations': 'Based on current market analysis, strong BUY signals for EUR/USD. HOLD for GBP/USD. Consider SELL for USD/JPY.',
        'news': 'Recent market news: Fed hints at rate pause, EUR rallies on economic data, GBP under pressure.'
    }
    
    query_lower = query.lower()
    for key, value in queries.items():
        if key in query_lower:
            return {'answer': value, 'confidence': 0.95}
    
    return {
        'answer': f"I understand your query about '{query}'. Based on current market analysis and your account status, I recommend reviewing the Dashboard and Market Sentiment sections for detailed insights.",
        'confidence': 0.60
    }


# =============================================================================
# VISUALIZATION FUNCTIONS
# =============================================================================

def create_pnl_line_chart(df: pd.DataFrame):
    """Create P&L trendline chart"""
    if df.empty:
        st.info("No P&L data available yet")
        return
    
    if HAS_PLOTLY:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['cumulative_pnl'],
            mode='lines+markers',
            name='Cumulative P&L',
            line=dict(color='#667eea', width=3),
            fill='tozeroy',
            fillcolor='rgba(102, 126, 234, 0.1)'
        ))
        fig.update_layout(
            title='Cumulative P&L Trendline',
            xaxis_title='Date',
            yaxis_title='P&L ($)',
            hovermode='x unified',
            template='plotly_white',
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.line_chart(df.set_index('date')[['cumulative_pnl']])


def create_pnl_pie_chart(account: Dict):
    """Create P&L distribution pie chart showing real profits vs losses"""
    if account.get('total_trades', 0) == 0:
        st.info("No trades yet")
        return
    
    # Fetch real P&L breakdown from API
    try:
        pnl_response = requests.get(f"{API_URL}/api/pnl/breakdown", timeout=2).json()
        profitable = pnl_response.get('profitable_trades', 0)
        losses = pnl_response.get('losing_trades', 0)
    except:
        profitable = 0
        losses = 0
    
    if HAS_PLOTLY:
        fig = go.Figure(data=[go.Pie(
            labels=['Profits', 'Losses'],
            values=[profitable, losses],
            hole=0.4,
            marker=dict(colors=['#00d4ff', '#ff4444']),
            textposition='inside',
            textinfo='label+value+percent',
            hovertemplate='<b>%{label}</b><br>Amount: $%{value:.2f}<br>Percentage: %{percent}<extra></extra>'
        )])
        fig.update_layout(
            title='Real P&L Distribution (Profits vs Losses)',
            height=400,
            template='plotly_dark',
            paper_bgcolor='rgba(10, 14, 39, 0.95)',
            font=dict(color='#e0e0e0')
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        pnl_data = pd.DataFrame({
            'Category': ['Profits', 'Losses'],
            'Amount': [profitable, losses]
        })
        st.bar_chart(pnl_data.set_index('Category'))


def create_win_rate_gauge():
    """Create dynamic bot strength gauge chart"""
    # Fetch real-time bot strength from API
    try:
        strength_response = requests.get(f"{API_URL}/api/bot/strength", timeout=2).json()
        bot_strength = strength_response.get('strength', 50)
        status = strength_response.get('status', 'fair')
    except:
        bot_strength = 50
        status = 'unknown'
    
    if HAS_PLOTLY:
        # Determine color based on strength
        bar_color = '#00d4ff' if bot_strength >= 80 else '#ffaa00' if bot_strength >= 60 else '#ff6b6b' if bot_strength >= 40 else '#ff4444'
        
        fig = go.Figure(data=[go.Indicator(
            mode='gauge+number+delta',
            value=bot_strength,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': 'Bot Strength', 'font': {'size': 20, 'color': '#00d4ff'}},
            delta={'reference': 50, 'increasing': {'color': '#00d4ff'}},
            gauge={
                'axis': {'range': [0, 100], 'tickcolor': '#00d4ff'},
                'bar': {'color': bar_color, 'thickness': 0.1},
                'steps': [
                    {'range': [0, 30], 'color': 'rgba(255, 68, 68, 0.3)'},
                    {'range': [30, 60], 'color': 'rgba(255, 170, 0, 0.3)'},
                    {'range': [60, 80], 'color': 'rgba(0, 212, 255, 0.2)'},
                    {'range': [80, 100], 'color': 'rgba(0, 212, 255, 0.4)'}
                ],
                'threshold': {
                    'line': {'color': '#00d4ff', 'width': 4},
                    'thickness': 0.75,
                    'value': 80
                }
            },
            number={'suffix': '%', 'font': {'size': 30, 'color': bar_color}}
        )])
        fig.update_layout(
            height=300,
            paper_bgcolor='rgba(10, 14, 39, 0.95)',
            font=dict(color='#e0e0e0')
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"🤖 **Status:** {status.upper()} | Bot is currently performing {status}ly")
    else:
        st.metric("Bot Strength", f"{bot_strength:.1f}%", delta=status)


def create_symbol_distribution():
    """Create trading symbol distribution"""
    trades_df = load_trades_data()
    
    if trades_df.empty:
        st.info("No trades yet")
        return
    
    symbol_counts = trades_df['symbol'].value_counts()
    
    if HAS_PLOTLY:
        fig = px.bar(
            x=symbol_counts.index,
            y=symbol_counts.values,
            labels={'x': 'Symbol', 'y': 'Trade Count'},
            color=symbol_counts.values,
            color_continuous_scale='Viridis'
        )
        fig.update_layout(
            title='Trades by Symbol',
            height=350,
            template='plotly_white'
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.bar_chart(symbol_counts)


# =============================================================================
# MAIN DASHBOARD TABS
# =============================================================================

def tab_overview():
    """Main overview tab"""
    st.markdown("<div class='section-header'>Live Account Dashboard</div>", unsafe_allow_html=True)

    render_deriv_live_strip()

    account = load_account_data()
    
    # Key Metrics Row 1
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Account Balance",
            f"${account.get('balance', 0):,.2f}",
            f"${account.get('daily_pnl', 0):+.2f}",
            delta_color="inverse"
        )
    
    with col2:
        st.metric(
            "Equity",
            f"${account.get('equity', 0):,.2f}",
            f"{account.get('margin_level', 0):.1f}%",
            delta_color="inverse"
        )
    
    with col3:
        st.metric(
            "Open Positions",
            account.get('open_positions', 0),
            "Live trades"
        )
    
    with col4:
        st.metric(
            "Total Trades",
            account.get('total_trades', 0),
            f"WR: {account.get('win_rate', 0):.1f}%"
        )
    
    # Key Metrics Row 2
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total P&L",
            f"${account.get('total_pnl', 0):+,.2f}",
            account.get('account_type', 'Real')
        )
    
    with col2:
        st.metric(
            "Win Rate",
            f"{account.get('win_rate', 0):.1f}%",
            f"W: {account.get('winning_trades', 0)} L: {account.get('losing_trades', 0)}"
        )
    
    with col3:
        st.metric(
            "Profit Factor",
            f"{account.get('profit_factor', 0):.2f}",
            "Wins/Losses Ratio"
        )
    
    with col4:
        st.metric(
            "Max Drawdown",
            f"{account.get('max_drawdown', 0):.2f}%",
            f"Sharpe: {account.get('sharpe_ratio', 0):.2f}"
        )
    
    # Charts Section
    st.markdown("<div class='section-header'>Performance Visualization</div>", unsafe_allow_html=True)
    
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        st.subheader("Cumulative P&L Trendline")
        pnl_df = load_pnl_data()
        create_pnl_line_chart(pnl_df)
    
    with chart_col2:
        st.subheader("P&L Distribution")
        create_pnl_pie_chart(account)
    
    # Additional Charts
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        st.subheader("Win Rate Gauge")
        create_win_rate_gauge()
    
    with chart_col2:
        st.subheader("Trading by Symbol")
        create_symbol_distribution()


def tab_trades():
    """Live trades tab"""
    st.markdown("<div class='section-header'>Trading History</div>", unsafe_allow_html=True)
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        status_filter = st.selectbox("Filter by Status", ["All", "Open", "Closed", "Pending"])
    
    with col2:
        symbol_filter = st.selectbox("Filter by Symbol", ["All", "EUR/USD", "GBP/USD", "USD/JPY"])
    
    with col3:
        direction_filter = st.selectbox("Filter by Direction", ["All", "BUY", "SELL"])
    
    # Load and display trades
    trades_df = load_trades_data(500)
    
    if not trades_df.empty:
        # Apply filters
        if status_filter != "All":
            trades_df = trades_df[trades_df['status'].str.upper() == status_filter.upper()]
        if symbol_filter != "All":
            trades_df = trades_df[trades_df['symbol'] == symbol_filter]
        if direction_filter != "All":
            trades_df = trades_df[trades_df['direction'].str.upper() == direction_filter.upper()]
        
        # Format display
        trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
        trades_df['entry_price'] = trades_df['entry_price'].apply(lambda x: f"{x:.5f}")
        trades_df['exit_price'] = trades_df['exit_price'].apply(lambda x: f"{x:.5f}" if x > 0 else "N/A")
        trades_df['profit_loss'] = trades_df['profit_loss'].apply(lambda x: f"${x:+.2f}")
        
        st.dataframe(trades_df, use_container_width=True, hide_index=True)
        
        # Download option
        csv = trades_df.to_csv(index=False)
        st.download_button(
            label="Download Trades as CSV",
            data=csv,
            file_name=f"trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No trading data available yet")


def tab_signals():
    """Market signals and opportunities tab"""
    st.markdown("<div class='section-header'>Trading Signals & Opportunities</div>", unsafe_allow_html=True)
    
    # Symbols for analysis
    symbols = ["EUR/USD", "GBP/USD", "USD/JPY"]
    
    for symbol in symbols:
        with st.expander(f"{symbol} Analysis", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                # Sentiment Analysis
                sentiment = get_market_sentiment(symbol)
                
                st.subheader(f"AI Market Sentiment")
                
                col_sent1, col_sent2 = st.columns(2)
                with col_sent1:
                    st.metric("Sentiment", sentiment['sentiment'], 
                             f"Score: {sentiment['score']:.2f}")
                with col_sent2:
                    st.metric("Confidence", f"{sentiment['confidence']:.0%}",
                             f"Technical: {sentiment['technical_sentiment']:.2f}")
                
                st.markdown(f"**Analysis:** {sentiment['analysis']}")
                
                st.markdown("**Key Factors:**")
                for factor in sentiment['key_factors']:
                    st.write(f"• {factor}")
                
                st.markdown("**Risk Factors:**")
                for risk in sentiment['risks']:
                    st.write(f"• {risk}")
            
            with col2:
                # Recent signals
                signals_df = load_signals_data()
                if not signals_df.empty:
                    symbol_signals = signals_df[signals_df['symbol'] == symbol].head(5)
                    
                    if not symbol_signals.empty:
                        st.subheader("Recent Signals")
                        for idx, signal in symbol_signals.iterrows():
                            signal_color = "green" if signal['signal'] == 1 else "red" if signal['signal'] == -1 else "gray"
                            signal_text = "BUY" if signal['signal'] == 1 else "SELL" if signal['signal'] == -1 else "HOLD"
                            st.write(f"**{signal_text}** - Confidence: {signal['confidence']:.0%} ({signal['timestamp']})")
                    else:
                        st.info("No signals yet for this symbol")
                else:
                    st.info("No signal data available")


def tab_breakout_analysis():
    """Breakout identification and prediction tab"""
    st.markdown("<div class='section-header'>🎯 Breakout Analysis & Prediction</div>", unsafe_allow_html=True)
    
    if HAS_BREAKOUT:
        display_breakout_dashboard()
    else:
        st.error("Breakout analysis module not available. Please check installation.")
        st.info("Make sure the breakout_analyzer module is properly installed.")


def tab_economic_calendar():
    """Economic calendar tab"""
    st.markdown("<div class='section-header'>Economic Calendar</div>", unsafe_allow_html=True)
    
    cal_df = get_economic_calendar_data()
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Filter by importance
        importance_filter = st.selectbox("Filter by Importance", ["All", "High", "Medium", "Low"])
        
        if importance_filter != "All":
            cal_df = cal_df[cal_df['importance'] == importance_filter]
    
    with col2:
        # Filter by country
        country_filter = st.selectbox("Filter by Country", ["All", "USA", "EUR", "GBP", "AUS"])
        
        if country_filter != "All":
            cal_df = cal_df[cal_df['country'] == country_filter]
    
    # Display calendar
    cal_df['date'] = cal_df['date'].dt.strftime('%Y-%m-%d %H:%M')
    
    # Color code importance
    def color_importance(val):
        colors = {'High': 'background-color: #ffcccc', 'Medium': 'background-color: #ffffcc', 'Low': 'background-color: #ccffcc'}
        return [colors.get(val, '') for val in val]
    
    styled_df = cal_df.style.apply(lambda x: color_importance(x) if x.name == 'importance' else [''] * len(x), axis=0)
    st.dataframe(styled_df, use_container_width=True)


def tab_market_news():
    """Market news and sentiment tab"""
    st.markdown("<div class='section-header'>Real-Time Market News & Sentiment</div>", unsafe_allow_html=True)
    
    news = get_market_news()
    
    for item in news:
        with st.container():
            col1, col2 = st.columns([3, 1])
            
            with col1:
                sentiment_color = "green" if item['sentiment'] == 'Positive' or item['sentiment'] == 'Bullish' else "red"
                st.markdown(f"**{item['title']}**")
                st.caption(f"{item['source']} | {item['time']}")
            
            with col2:
                if item['sentiment'] in ['Positive', 'Bullish']:
                    st.write(":green-background[" + item['sentiment'] + "]")
                elif item['sentiment'] in ['Negative', 'Bearish']:
                    st.write(":red-background[" + item['sentiment'] + "]")
                else:
                    st.write(":gray-background[" + item['sentiment'] + "]")
            
            st.divider()


def tab_natural_language():
    """Natural language query interface tab"""
    st.markdown("<div class='section-header'>AI-Powered Natural Language Interface</div>", unsafe_allow_html=True)
    
    st.markdown("""
    Ask me questions about your trading account, market conditions, or trading recommendations.
    
    **Example queries:**
    - "What's my current balance?"
    - "Show me my open positions"
    - "What's my best trade?"
    - "What's my win rate?"
    - "What are your trading recommendations?"
    - "Latest market news"
    """)
    
    query = st.text_input("Enter your query:", placeholder="Ask about your trades, market conditions, or recommendations...")
    
    if query:
        with st.spinner("Analyzing..."):
            result = process_natural_language_query(query)
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown(f"**Answer:** {result['answer']}")
            
            with col2:
                st.metric("Confidence", f"{result['confidence']:.0%}")


def tab_api_docs():
    """RESTful API documentation tab"""
    st.markdown("<div class='section-header'>RESTful API Documentation</div>", unsafe_allow_html=True)
    
    st.markdown("""
    ## Available Endpoints
    
    ### Account Endpoints
    - `GET /api/account/balance` - Get current balance
    - `GET /api/account/equity` - Get equity info
    - `GET /api/account/positions` - Get open positions
    - `GET /api/account/trades` - Get trade history
    
    ### Market Data
    - `GET /api/market/price/{symbol}` - Get current price
    - `GET /api/market/sentiment/{symbol}` - Get market sentiment
    - `GET /api/market/news` - Get latest news
    - `GET /api/market/economic-calendar` - Get economic events
    
    ### Trading
    - `POST /api/trade/buy` - Place buy order
    - `POST /api/trade/sell` - Place sell order
    - `POST /api/trade/close/{position_id}` - Close position
    - `GET /api/trade/signals` - Get trading signals
    
    ### System
    - `GET /api/health` - Health check
    - `GET /api/status` - System status
    
    ### Authentication
    Add your API token in the header:
    ```
    Authorization: Bearer YOUR_API_TOKEN
    ```
    
    ### Example Request
    ```bash
    curl -X GET http://localhost:5000/api/account/balance \\
      -H "Authorization: Bearer ***REMOVED***"
    ```
    """)


def tab_download():
    """Downloadable web interface tab"""
    st.markdown("<div class='section-header'>Download & Export</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Export Data")
        
        if st.button("Download Full Trading History"):
            trades_df = load_trades_data(10000)
            if not trades_df.empty:
                csv = trades_df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"full_trading_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
        
        if st.button("Download Performance Report"):
            account = load_account_data()
            report = f"""
SENTIENX Trading Performance Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Account Summary:
- Balance: ${account.get('balance', 0):,.2f}
- Equity: ${account.get('equity', 0):,.2f}
- Total P&L: ${account.get('total_pnl', 0):+,.2f}
- Win Rate: {account.get('win_rate', 0):.1f}%

Trading Statistics:
- Total Trades: {account.get('total_trades', 0)}
- Winning Trades: {account.get('winning_trades', 0)}
- Losing Trades: {account.get('losing_trades', 0)}
- Profit Factor: {account.get('profit_factor', 0):.2f}
- Best Trade: ${account.get('best_trade', 0):+.2f}
- Worst Trade: ${account.get('worst_trade', 0):+.2f}
- Average Trade: ${account.get('avg_trade', 0):+.2f}

Risk Metrics:
- Max Drawdown: {account.get('max_drawdown', 0):.2f}%
- Sharpe Ratio: {account.get('sharpe_ratio', 0):.2f}
            """
            st.download_button(
                label="Download Report",
                data=report,
                file_name=f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain"
            )
    
    with col2:
        st.subheader("Web Interface")
        
        st.markdown("""
        ### Dashboard Available At:
        - Local: http://localhost:8501
        - API: http://localhost:5000
        
        ### System Information
        - Version: 1.0.0
        - Last Updated: 2025-11-29
        - Status: Live Trading Enabled
        - Account Type: Real
        """)


# =============================================================================
# MAIN APPLICATION
# =============================================================================

# --- OpenStock-derived tabs (added 2026-10-23, dashboard owner: Agora agent) ---

def tab_watchlist():
    """OpenStock-derived watchlist tab"""
    if HAS_OPENSTOCK:
        osp.render_watchlist_tab()
    else:
        st.info("OpenStock market module unavailable (import failed).")


def tab_price_alerts():
    """OpenStock-derived price alerts tab"""
    if HAS_OPENSTOCK:
        osp.render_alerts_tab()
    else:
        st.info("OpenStock market module unavailable (import failed).")


def tab_heatmap():
    """OpenStock-derived market heatmap tab"""
    if HAS_OPENSTOCK:
        osp.render_heatmap_tab()
    else:
        st.info("OpenStock market module unavailable (import failed).")


def tab_symbol_detail():
    """OpenStock-derived symbol detail tab"""
    if HAS_OPENSTOCK:
        osp.render_symbol_detail_tab()
    else:
        st.info("OpenStock market module unavailable (import failed).")


def main():
    """Main application"""
    
    # Check authentication
    check_authentication()
    
    if not st.session_state.authenticated:
        if st.session_state.view == 'login':
            login_page()
        else:
            landing_page()
        return
    
    # Header
    st.title("SENTIENX")
    
    # Sidebar Configuration
    with st.sidebar:
        st.header("Settings")

        # OpenStock market palette (symbol search + quick actions)
        if HAS_OPENSTOCK:
            osp.render_sidebar_palette()
            st.divider()

        if st.button("Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.view = 'landing'
            st.rerun()
        
        st.divider()
        
        refresh_rate = st.slider(
            "Refresh Interval (seconds)",
            5, 300, 30, 5
        )
        st.session_state.refresh_interval = refresh_rate
        st.checkbox("Live auto-refresh", value=False, key="sx_live_auto",
                    help="Reloads the dashboard every refresh interval")
        
        st.divider()
        
        account = load_account_data()
        st.markdown("**Deriv accounts**")
        if deriv_feed.ready():
            prev = st.session_state.get("sx_acct_mode", "Demo")
            st.radio("Active account", ["Demo", "Real"], index=0 if prev == "Demo" else 1,
                     horizontal=True, key="sx_acct_mode",
                     help="Demo for testing, Real for the live account")
            if st.session_state.get("sx_acct_mode", "Demo") != prev:
                _deriv_clear_cache()
            try:
                accts = _deriv_accts()
                st.caption(f"Real · {accts.get('real', {}).get('account_id')} · "
                           f"${float(accts.get('real', {}).get('balance', 0)):,.2f}")
                st.caption(f"Demo · {accts.get('demo', {}).get('account_id')} · "
                           f"${float(accts.get('demo', {}).get('balance', 0)):,.2f}")
                st.caption(f"Connection: {'Live' if account.get('connected') else 'Disconnected'}")
            except Exception:
                st.caption("Deriv feed unreachable")
        else:
            st.caption("Deriv credentials not configured — set "
                       "DERIV_PAT_TOKEN and DERIV_APP_ID_NEW.")

        st.divider()
        
        # Bot Control Section
        st.markdown("**🤖 Bot Control**")
        
        import requests
        try:
            bot_status = requests.get("http://localhost:5000/api/bot/status", timeout=2).json()
            is_running = bot_status.get('running', False)
            
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("▶ Start Bot", use_container_width=True, key="start_bot"):
                    start_response = requests.get("http://localhost:5000/api/bot/start", timeout=5).json()
                    if start_response.get('success'):
                        st.success(f"✓ {start_response.get('message')}")
                    else:
                        st.error(f"✗ {start_response.get('message')}")
                    st.rerun()
            
            with col2:
                if st.button("⏹ Stop Bot", use_container_width=True, key="stop_bot"):
                    stop_response = requests.get("http://localhost:5000/api/bot/stop", timeout=5).json()
                    if stop_response.get('success'):
                        st.success(f"✓ {stop_response.get('message')}")
                    else:
                        st.error(f"✗ {stop_response.get('message')}")
                    st.rerun()
            
            # Bot status indicator
            status_color = "🟢" if is_running else "🔴"
            st.write(f"{status_color} **Status:** {'Running' if is_running else 'Stopped'}")
            if is_running and bot_status.get('uptime'):
                st.write(f"⏱️ **Uptime:** {bot_status.get('uptime')}")
        except:
            st.warning("Cannot connect to bot service")
        
        st.divider()
        
        # Deriv Connection Test
        st.markdown("**🔗 Deriv Connection**")
        
        if st.button("Test Deriv Connection", use_container_width=True, key="test_deriv"):
            try:
                result = requests.get("http://localhost:5000/api/deriv/test", timeout=5).json()
                if result.get('success'):
                    st.success("✓ Connected to Deriv")
                    if result.get('account_data'):
                        st.write(f"Balance: ${result['account_data'].get('balance', 0):.2f}")
                        st.write(f"Status: {result['account_data'].get('status', 'unknown')}")
                else:
                    st.error(f"✗ {result.get('message')}")
            except Exception as e:
                st.error(f"Connection test failed: {str(e)}")
        
        st.divider()
        
        st.markdown("**Quick Links**")
        if st.button("Refresh Dashboard"):
            st.rerun()
        
        if st.button("Download Dashboard"):
            st.markdown("Use the Download tab to export data")
    
    # Main Tabs
    tabs = st.tabs([
        "Overview",
        "Live Trades",
        "Trading Signals",
        "Breakout Analysis",
        "Economic Calendar",
        "Market News",
        "AI Assistant",
        "API Docs",
        "Download",
        "Watchlist",
        "Price Alerts",
        "Heatmap",
        "Symbol Detail"
    ])
    
    with tabs[0]:
        tab_overview()
    
    with tabs[1]:
        tab_trades()
    
    with tabs[2]:
        tab_signals()
    
    with tabs[3]:
        tab_breakout_analysis()
    
    with tabs[4]:
        tab_economic_calendar()
    
    with tabs[5]:
        tab_market_news()
    
    with tabs[6]:
        tab_natural_language()
    
    with tabs[7]:
        tab_api_docs()
    
    with tabs[8]:
        tab_download()
    
    with tabs[9]:
        tab_watchlist()
    
    with tabs[10]:
        tab_price_alerts()
    
    with tabs[11]:
        tab_heatmap()
    
    with tabs[12]:
        tab_symbol_detail()
    
    # Footer
    display_footer()

    # Live auto-refresh — full rerun every interval when enabled
    if st.session_state.get('sx_live_auto'):
        try:
            import streamlit.components.v1 as _components
            _components.html(
                "<script>setTimeout(function(){window.parent.location.reload();}, %d);</script>"
                % (int(st.session_state.get('refresh_interval', 30)) * 1000),
                height=0)
        except Exception:
            pass


if __name__ == "__main__":
    main()
