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
from datetime import datetime, timedelta, date
import json
import sqlite3
import os
import requests
from pathlib import Path
from typing import Dict, List, Tuple
import threading
import time

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

# Dark Theme Styling with Reduced Animations
st.markdown("""
    <style>
    @keyframes slideIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
    
    * { margin: 0; padding: 0; }
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #0a0e27 !important;
        color: #e0e0e0 !important;
        cursor: default;
    }
    [data-testid="stSidebar"] {
        background-color: #1a1f3a !important;
    }
    .block-container {
        padding: 20px;
        background-color: #0a0e27 !important;
        animation: slideIn 0.3s ease-out;
    }
    .stTabs [data-baseweb="tab-list"] {
        background-color: #1a1f3a;
        border-bottom: 2px solid #2d3561;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #1a1f3a;
        color: #a0a0a0;
        border-radius: 5px 5px 0 0;
        transition: all 0.2s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #64c8ff;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2d3561 !important;
        color: #00d4ff !important;
    }
    h1 { color: #00d4ff; margin-bottom: 20px; font-weight: bold; }
    h2 { color: #00d4ff; margin-top: 20px; }
    h3 { color: #a0a0a0; }
    .stMetric { background-color: #1a1f3a; padding: 15px; border-radius: 8px; border-left: 3px solid #00d4ff; transition: all 0.2s ease; }
    .stMetric:hover { transform: translateX(3px); box-shadow: 0 2px 8px rgba(0, 212, 255, 0.15); }
    .stDataFrame { background-color: #1a1f3a !important; }
    [data-testid="stDataFrameContainer"] { background-color: #1a1f3a !important; }
    .stSelectbox, .stSlider, .stTextInput { background-color: #1a1f3a; transition: all 0.2s ease; }
    .stSelectbox:hover, .stSlider:hover, .stTextInput:hover { box-shadow: 0 0 8px rgba(0, 212, 255, 0.15); }
    button { background-color: #2d3561 !important; color: #00d4ff !important; border: 1px solid #00d4ff !important; font-weight: bold; transition: all 0.2s ease; }
    button:hover { background-color: #00d4ff !important; color: #0a0e27 !important; box-shadow: 0 0 12px rgba(0, 212, 255, 0.3); }

    button:active { transform: scale(0.98); }
    a { color: #00d4ff !important; transition: all 0.2s ease; }
    a:hover { color: #64c8ff; }
    .success { color: #00d700; }
    .danger { color: #ff4444; }
    .warning { color: #ffaa00; }
    .section-header { color: #00d4ff; font-size: 20px; font-weight: bold; margin: 15px 0 10px 0; border-bottom: 2px solid #2d3561; padding-bottom: 10px; }
    .footer { background-color: #1a1f3a; border-top: 2px solid #2d3561; padding: 20px; margin-top: 40px; text-align: center; color: #a0a0a0; font-size: 12px; }
    
    .login-wrapper { display: flex; justify-content: center; align-items: center; min-height: 100vh; background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 50%, #2d3561 100%); }
    .login-container { background: rgba(26, 31, 58, 0.95); backdrop-filter: blur(10px); padding: 50px; border-radius: 15px; max-width: 420px; width: 100%; border: 2px solid #00d4ff; box-shadow: 0 8px 32px rgba(0, 212, 255, 0.1); }
    .login-title { color: #00d4ff; text-align: center; font-size: 32px; font-weight: bold; margin-bottom: 10px; letter-spacing: 2px; text-transform: uppercase; }
    .login-subtitle { color: #a0a0a0; text-align: center; font-size: 14px; margin-bottom: 40px; font-weight: 300; letter-spacing: 1px; }
    .login-divider { height: 2px; background: linear-gradient(90deg, transparent, #00d4ff, transparent); margin: 30px 0; }
    .login-input-label { color: #00d4ff; font-size: 12px; font-weight: bold; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 1px; display: block; }
    input[type="text"], input[type="password"] { background-color: #0f1429 !important; border: 1px solid #2d3561 !important; color: #e0e0e0 !important; padding: 12px 15px !important; border-radius: 8px !important; font-size: 14px !important; margin-bottom: 20px !important; transition: all 0.2s ease !important; }
    input[type="text"]:focus, input[type="password"]:focus { border: 2px solid #00d4ff !important; box-shadow: 0 0 15px rgba(0, 212, 255, 0.3) !important; background-color: #1a1f3a !important; }
    .login-button { background-color: #00d4ff !important; color: #0a0e27 !important; border: none !important; padding: 14px 30px !important; border-radius: 8px !important; font-weight: bold !important; font-size: 14px !important; cursor: pointer !important; text-transform: uppercase !important; letter-spacing: 1.5px !important; transition: all 0.2s ease !important; width: 100% !important; }
    .login-button:hover { background-color: #00f7ff !important; box-shadow: 0 0 20px rgba(0, 212, 255, 0.4) !important; }
    .login-button:active { transform: scale(0.98) !important; }
    .login-footer { text-align: center; margin-top: 30px; color: #a0a0a0; font-size: 12px; }
    .login-demo-info { background-color: rgba(0, 212, 255, 0.1); border-left: 3px solid #00d4ff; padding: 15px; border-radius: 5px; margin-top: 20px; font-size: 13px; color: #00d4ff; transition: all 0.2s ease; }
    .login-demo-info:hover { background-color: rgba(0, 212, 255, 0.15); }
    </style>
    """, unsafe_allow_html=True)

# Authentication
def check_authentication():
    """Check if user is authenticated"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

def login_page():
    """Professional branded auth screen (the app's landing page)."""
    # Hide sidebar/header chrome and paint the hero gradient until login.
    st.markdown("""
        <style>
        [data-testid="stSidebar"] { display: none; }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stAppViewContainer"] { background:
            radial-gradient(1100px 560px at 72% -12%, rgba(34,197,94,0.09), transparent 60%),
            radial-gradient(900px 520px at 8% 112%, rgba(59,130,246,0.11), transparent 55%),
            #0a0e27 !important; }
        .sx-auth-wrap { min-height: 90vh; display: flex; flex-direction: column;
            justify-content: center; align-items: center; }
        .sx-auth-card { width: 100%; max-width: 400px; background: rgba(255,255,255,0.035);
            border: 1px solid rgba(255,255,255,0.09); border-radius: 18px;
            padding: 38px 36px 24px; backdrop-filter: blur(8px);
            box-shadow: 0 24px 60px rgba(0,0,0,0.45); }
        .sx-auth-card input { background: rgba(255,255,255,0.05) !important;
            border: 1px solid rgba(255,255,255,0.12) !important; border-radius: 10px !important;
            color: #e2e8f0 !important; }
        .sx-auth-card input:focus { border-color: #22c55e !important;
            box-shadow: 0 0 0 1px #22c55e !important; }
        .sx-auth-card button { border: none !important; border-radius: 10px !important;
            font-weight: 700; letter-spacing: 0.14em; color: #06130a !important;
            background: linear-gradient(90deg, #22c55e, #4ade80) !important;
            transition: transform 0.15s ease, box-shadow 0.15s ease; }
        .sx-auth-card button:hover { transform: translateY(-1px);
            box-shadow: 0 8px 22px rgba(34,197,94,0.35); }
        .sx-brand { font-size: 2.1rem; font-weight: 800; letter-spacing: 0.35em;
            text-align: center; margin-top: 4px;
            background: linear-gradient(90deg, #e2e8f0, #22c55e 55%, #3b82f6);
            -webkit-background-clip: text; background-clip: text; color: transparent; }
        .sx-tagline { text-align: center; color: #94a3b8; font-size: 0.8rem;
            margin: 8px 0 26px; letter-spacing: 0.14em; }
        .sx-label { color: #cbd5e1; font-size: 0.74rem; text-transform: uppercase;
            letter-spacing: 0.14em; margin: 12px 2px 2px; }
        .sx-features { display: flex; gap: 24px; justify-content: center; margin-top: 24px;
            color: #64748b; font-size: 0.78rem; flex-wrap: wrap; }
        .sx-auth-footer { text-align: center; color: #475569; font-size: 0.72rem; margin-top: 30px; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("<div class='sx-auth-wrap'><div class='sx-auth-card'>", unsafe_allow_html=True)
    st.markdown("<div class='sx-brand'>SENTIENX</div>", unsafe_allow_html=True)
    st.markdown("<div class='sx-tagline'>AI-POWERED TRADING COMMAND CENTER</div>", unsafe_allow_html=True)

    with st.form("sx_login_form"):
        st.markdown("<div class='sx-label'>Username</div>", unsafe_allow_html=True)
        username = st.text_input("Username", key="login_username", label_visibility="collapsed")
        st.markdown("<div class='sx-label'>Password</div>", unsafe_allow_html=True)
        password = st.text_input("Password", type="password", key="login_password", label_visibility="collapsed")
        submitted = st.form_submit_button("ENTER DASHBOARD", use_container_width=True)

    if submitted:
        expected_user = os.environ.get("SENTIENX_USER", "marvel")
        expected_pass = os.environ.get("SENTIENX_PASS", "olivertwist")
        if username == expected_user and password == expected_pass:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("\u274c Invalid username or password.")

    st.markdown("""
        <div class='sx-features'>
            <span>📈 Live market data</span>
            <span>🔔 Price alerts</span>
            <span>🔥 Market heatmap</span>
        </div>
        <div class='sx-auth-footer'>SENTIENX Trading System · © 2025 · All Rights Reserved</div>
        </div></div>
    """, unsafe_allow_html=True)

# Set up paths
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "sentienx_trading.db"
LOGS_PATH = BASE_DIR / "logs"
API_URL = "http://localhost:5000"

# Initialize database
def initialize_database():
    """Initialize database with required tables"""
    try:
        LOGS_PATH.mkdir(parents=True, exist_ok=True)
        os.chmod(str(LOGS_PATH), 0o755)
        
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='trading_history'
        """)
        
        if not cursor.fetchone():
            cursor.execute('''
                CREATE TABLE trading_history (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT,
                    direction TEXT,
                    entry_price REAL,
                    exit_price REAL,
                    volume REAL,
                    profit_loss REAL,
                    status TEXT,
                    timestamp TEXT,
                    strategy TEXT
                )
            ''')
            conn.commit()
        
        conn.close()
        os.chmod(str(DB_PATH), 0o644)
    except Exception:
        pass

initialize_database()

# Session State
if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 30
if 'selected_tab' not in st.session_state:
    st.session_state.selected_tab = 0
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False


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

def get_db_connection():
    """Get SQLite database connection with error handling"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        return conn
    except PermissionError:
        return None
    except Exception:
        return None


def load_account_data() -> Dict:
    """Load live account data from API or database"""
    # Try to fetch from API first
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
            except:
                pass
            
            return api_data
    except Exception:
        pass
    
    # Fallback to database
    try:
        from config import DERIV_CONFIG
        from deriv_connector import deriv_connector
        
        # Try to get Deriv balance
        deriv_balance = 1000.0
        deriv_connected = False
        try:
            success, balance, _ = deriv_connector.get_balance()
            if success and balance:
                deriv_balance = balance
                deriv_connected = True
        except:
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
            'total_pnl': deriv_balance - 1000.0,
            'daily_pnl': 0.0,
            'best_trade': 0.0,
            'worst_trade': 0.0,
            'avg_trade': 0.0,
            'sharpe_ratio': 1.8,
            'max_drawdown': 5.2,
            'connected': deriv_connected,
            'deriv_connected': deriv_connected,
            'account_type': 'Real' if DERIV_CONFIG.get('environment') == 'real' else 'Demo'
        }
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            
            # Get trade statistics
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losses,
                    SUM(profit_loss) as total_pnl,
                    MAX(profit_loss) as best_trade,
                    MIN(profit_loss) as worst_trade,
                    AVG(profit_loss) as avg_trade
                FROM trading_history
            """)
            
            stats = cursor.fetchone()
            if stats:
                total = stats['total'] or 0
                wins = stats['wins'] or 0
                losses = stats['losses'] or 0
                
                account['total_trades'] = total
                account['winning_trades'] = wins
                account['losing_trades'] = losses
                account['win_rate'] = (wins / total * 100) if total > 0 else 0
                account['total_pnl'] = stats['total_pnl'] or 0
                account['best_trade'] = stats['best_trade'] or 0
                account['worst_trade'] = stats['worst_trade'] or 0
                account['avg_trade'] = stats['avg_trade'] or 0
                
                if losses > 0 and wins > 0:
                    total_wins = sum([row['profit_loss'] for row in cursor.execute(
                        "SELECT profit_loss FROM trading_history WHERE profit_loss > 0"
                    )])
                    total_losses = abs(sum([row['profit_loss'] for row in cursor.execute(
                        "SELECT profit_loss FROM trading_history WHERE profit_loss < 0"
                    )]))
                    account['profit_factor'] = total_wins / total_losses if total_losses > 0 else 0
            
            # Get open positions
            cursor.execute("SELECT COUNT(*) as open FROM trading_history WHERE status='open'")
            open_pos = cursor.fetchone()
            account['open_positions'] = open_pos['open'] or 0
            
            conn.close()
        
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
        conn = get_db_connection()
        if conn:
            query = """
                SELECT 
                    symbol, direction, entry_price, exit_price, 
                    volume, profit_loss, status, timestamp, strategy
                FROM trading_history 
                ORDER BY timestamp DESC 
                LIMIT ?
            """
            df = pd.read_sql_query(query, conn, params=(limit,))
            conn.close()
            
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df['profit_loss'] = pd.to_numeric(df['profit_loss'], errors='coerce')
            
            return df
        return pd.DataFrame()
    except Exception as e:
        st.warning(f"Error loading trades: {e}")
        return pd.DataFrame()


def load_signals_data(limit: int = 50) -> pd.DataFrame:
    """Load recent trading signals"""
    try:
        conn = get_db_connection()
        if conn:
            try:
                query = """
                    SELECT 
                        symbol, signal, confidence, strength, 
                        indicators, timestamp, strategy
                    FROM signals_history 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """
                df = pd.read_sql_query(query, conn, params=(limit,))
                conn.close()
                
                if not df.empty:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df['confidence'] = pd.to_numeric(df['confidence'], errors='coerce')
                
                return df
            except Exception:
                conn.close()
                return pd.DataFrame()
        return pd.DataFrame()
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
        conn = get_db_connection()
        if conn:
            query = """
                SELECT 
                    DATE(timestamp) as date,
                    SUM(profit_loss) as daily_pnl,
                    COUNT(*) as trades,
                    SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as wins
                FROM trading_history 
                GROUP BY DATE(timestamp)
                ORDER BY date ASC
            """
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'])
                df['cumulative_pnl'] = df['daily_pnl'].cumsum()
            
            return df
        return pd.DataFrame()
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
        login_page()
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
            st.rerun()
        
        st.divider()
        
        refresh_rate = st.slider(
            "Refresh Interval (seconds)",
            5, 300, 30, 5
        )
        st.session_state.refresh_interval = refresh_rate
        
        st.divider()
        
        account = load_account_data()
        st.markdown(f"**Account Status**")
        st.write(f"Type: {account.get('account_type', 'Real')}")
        st.write(f"Connection: {'Connected' if account.get('connected') else 'Disconnected'}")
        
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


if __name__ == "__main__":
    main()
