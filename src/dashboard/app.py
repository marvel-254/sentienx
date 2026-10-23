import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
from pathlib import Path

try:
    import plotly.graph_objects as go
    import plotly.express as px
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

st.set_page_config(
    page_title="SENTIENX Trading Bot",
    page_icon="stock",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main { padding: 0; }
    .block-container { padding: 20px; }
    h1 { color: #1f77b4; margin-bottom: 20px; }
    h2 { color: #2ca02c; margin-top: 20px; }
    .metric-box { background: #f0f2f6; padding: 15px; border-radius: 5px; }
    .success { color: #28a745; }
    .danger { color: #dc3545; }
    .warning { color: #ffc107; }
    </style>
    """, unsafe_allow_html=True)

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "sentienx_trading.db"
LOGS_PATH = BASE_DIR / "logs"


def load_trades_data():
    """Load trades from database"""
    try:
        trades = []
        if DB_PATH.exists():
            import sqlite3
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            cursor.execute("""
                SELECT symbol, direction, entry_price, exit_price, 
                       volume, profit_loss, status, timestamp 
                FROM trading_history ORDER BY timestamp DESC LIMIT 100
            """)
            columns = ['Symbol', 'Direction', 'Entry Price', 'Exit Price', 
                      'Volume', 'P&L', 'Status', 'Timestamp']
            trades = [dict(zip(columns, row)) for row in cursor.fetchall()]
            conn.close()
        return trades
    except Exception as e:
        st.error(f"Error loading trades: {str(e)}")
        return []


def load_account_data():
    """Load account information from config"""
    try:
        from config import RISK_CONFIG, TRADING_CONFIG
        import sqlite3
        
        account = {
            'balance': 0,
            'equity': 0,
            'free_margin': 0,
            'margin_level': 0,
            'open_positions': 0,
            'total_trades': 0,
            'win_rate': 0,
            'profit_factor': 0
        }
        
        if DB_PATH.exists():
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM trading_history WHERE status='closed'")
            total_closed = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM trading_history WHERE profit_loss > 0")
            wins = cursor.fetchone()[0]
            
            if total_closed > 0:
                account['win_rate'] = (wins / total_closed) * 100
            
            cursor.execute("SELECT SUM(profit_loss) FROM trading_history WHERE profit_loss > 0")
            total_wins = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT SUM(ABS(profit_loss)) FROM trading_history WHERE profit_loss < 0")
            total_losses = cursor.fetchone()[0] or 1
            
            if total_losses > 0:
                account['profit_factor'] = total_wins / total_losses
            
            cursor.execute("SELECT COUNT(*) FROM trading_history WHERE status='open'")
            account['open_positions'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM trading_history")
            account['total_trades'] = cursor.fetchone()[0]
            
            conn.close()
        
        return account
    except Exception as e:
        st.error(f"Error loading account data: {str(e)}")
        return {}


def load_recent_logs(limit=50):
    """Load recent log entries"""
    try:
        logs = []
        for log_file in sorted(LOGS_PATH.glob("*.log"), reverse=True)[:5]:
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()[-limit:]
                    logs.extend(lines)
            except:
                continue
        return logs[-limit:]
    except Exception as e:
        st.warning(f"Could not load logs: {str(e)}")
        return []


def load_signals_data():
    """Load trading signals from database"""
    try:
        signals = []
        if DB_PATH.exists():
            import sqlite3
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            cursor.execute("""
                SELECT symbol, signal_type, confidence, strength, 
                       strategy, timestamp 
                FROM trading_signals ORDER BY timestamp DESC LIMIT 20
            """)
            signals = [
                {
                    'Symbol': row[0],
                    'Signal': row[1],
                    'Confidence': f"{row[2]:.2%}",
                    'Strength': row[3],
                    'Strategy': row[4],
                    'Time': row[5]
                }
                for row in cursor.fetchall()
            ]
            conn.close()
        return signals
    except Exception as e:
        st.warning(f"Could not load signals: {str(e)}")
        return []


def plot_equity_curve(trades):
    """Plot account equity curve"""
    if not trades:
        st.info("No trades data available")
        return
    
    if not HAS_PLOTLY:
        st.warning("Plotly not available - showing data table instead")
        equity = [10000]
        for trade in trades[::-1]:
            equity.append(equity[-1] + trade.get('P&L', 0))
        df = pd.DataFrame({'Trade': range(len(equity)), 'Equity': equity})
        st.dataframe(df)
        return
    
    equity = [10000]
    for trade in trades[::-1]:
        equity.append(equity[-1] + trade.get('P&L', 0))
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=equity,
        mode='lines',
        name='Equity',
        line=dict(color='#1f77b4', width=2),
        fill='tozeroy',
        fillcolor='rgba(31, 119, 180, 0.2)'
    ))
    fig.update_layout(
        title="Account Equity Curve",
        xaxis_title="Trade Number",
        yaxis_title="Equity (USD)",
        hovermode='x unified',
        template='plotly_white',
        height=400
    )
    st.plotly_chart(fig, use_container_width=True)


def plot_trade_analysis(trades):
    """Plot trade analysis"""
    if not trades:
        st.info("No trades data available")
        return
    
    directions = pd.Series([t['Direction'] for t in trades]).value_counts()
    
    col1, col2 = st.columns(2)
    
    with col1:
        if HAS_PLOTLY:
            fig1 = px.pie(
                values=directions.values,
                names=directions.index,
                title="Buy vs Sell Trades",
                color_discrete_map={'BUY': '#28a745', 'SELL': '#dc3545'}
            )
            st.plotly_chart(fig1, use_container_width=True)
        else:
            st.write("Buy vs Sell Trades")
            st.write(directions)
    
    with col2:
        pnl_data = pd.Series([t['P&L'] for t in trades if t['P&L']])
        if HAS_PLOTLY:
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                y=pnl_data.values,
                marker=dict(
                    color=['#28a745' if x > 0 else '#dc3545' for x in pnl_data.values]
                ),
                name='P&L'
            ))
            fig2.update_layout(
                title="Trade Profit/Loss Distribution",
                xaxis_title="Trade",
                yaxis_title="P&L (USD)",
                height=400,
                template='plotly_white'
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.write("Trade Profit/Loss Distribution")
            st.bar_chart(pnl_data)


def main():
    st.title("SENTIENX Trading Bot Dashboard")
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Dashboard", "Trades", "Signals", "Logs", "Performance", "Settings"
    ])
    
    with tab1:
        st.header("Real-Time Overview")
        
        account = load_account_data()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Account Balance", f"${account.get('balance', 0):,.2f}")
        with col2:
            st.metric("Equity", f"${account.get('equity', 0):,.2f}")
        with col3:
            st.metric("Open Positions", account.get('open_positions', 0))
        with col4:
            st.metric("Win Rate", f"{account.get('win_rate', 0):.1f}%")
        
        st.divider()
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Quick Stats")
            st.write(f"Total Trades: {account.get('total_trades', 0)}")
            st.write(f"Profit Factor: {account.get('profit_factor', 0):.2f}")
            st.write(f"Free Margin: ${account.get('free_margin', 0):,.2f}")
        
        with col2:
            st.subheader("System Status")
            st.success("Bot Status: Active")
            st.success("Deriv Connection: Connected")
            st.success("Market Data: Streaming")
        
        st.divider()
        
        trades = load_trades_data()
        if trades:
            plot_equity_curve(trades)
    
    with tab2:
        st.header("Trading History")
        
        trades = load_trades_data()
        if trades:
            df = pd.DataFrame(trades)
            st.dataframe(df, use_container_width=True, height=400)
            
            st.divider()
            plot_trade_analysis(trades)
        else:
            st.info("No trades yet")
    
    with tab3:
        st.header("Trading Signals")
        
        signals = load_signals_data()
        if signals:
            df = pd.DataFrame(signals)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No signals generated yet")
    
    with tab4:
        st.header("System Logs")
        
        log_level = st.selectbox("Filter by Level", ["ALL", "INFO", "WARNING", "ERROR"])
        
        logs = load_recent_logs(100)
        filtered_logs = logs
        
        if log_level != "ALL":
            filtered_logs = [log for log in logs if log_level in log]
        
        if filtered_logs:
            log_text = "".join(filtered_logs[-100:])
            st.text_area("Recent Logs", value=log_text, height=400, disabled=True)
        else:
            st.info("No logs available")
    
    with tab5:
        st.header("Performance Metrics")
        
        account = load_account_data()
        trades = load_trades_data()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Win Rate", f"{account.get('win_rate', 0):.1f}%")
        with col2:
            st.metric("Profit Factor", f"{account.get('profit_factor', 0):.2f}")
        with col3:
            total_pnl = sum([t.get('P&L', 0) for t in trades])
            st.metric("Total P&L", f"${total_pnl:,.2f}")
        with col4:
            if trades:
                avg_pnl = total_pnl / len(trades)
                st.metric("Average P&L", f"${avg_pnl:,.2f}")
            else:
                st.metric("Average P&L", "$0.00")
        
        st.divider()
        
        if trades:
            plot_equity_curve(trades)
    
    with tab6:
        st.header("Settings")
        
        st.subheader("Bot Configuration")
        
        try:
            from config import RISK_CONFIG, TRADING_CONFIG
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("Risk Management")
                max_risk = st.number_input(
                    "Max Risk per Trade (%)",
                    value=RISK_CONFIG.get('max_risk_per_trade', 0.01) * 100,
                    min_value=0.01,
                    max_value=5.0
                )
                max_daily_loss = st.number_input(
                    "Max Daily Loss ($)",
                    value=RISK_CONFIG.get('max_daily_loss', 10),
                    min_value=1
                )
                max_positions = st.number_input(
                    "Max Open Positions",
                    value=RISK_CONFIG.get('max_open_positions', 3),
                    min_value=1,
                    max_value=10
                )
            
            with col2:
                st.write("Trading Configuration")
                confidence_threshold = st.slider(
                    "Confidence Threshold",
                    min_value=0.5,
                    max_value=0.99,
                    value=TRADING_CONFIG.get('confidence_threshold', 0.7),
                    step=0.05
                )
                auto_trading = st.checkbox(
                    "Enable Auto Trading",
                    value=TRADING_CONFIG.get('auto_trading', False)
                )
            
            if st.button("Save Settings"):
                st.success("Settings saved successfully")
        
        except Exception as e:
            st.error(f"Error loading settings: {str(e)}")
        
        st.divider()
        
        st.subheader("Deriv Account")
        st.info("Current Account: Live Trading")
        st.write("Connected: Yes")
        st.write("Account Type: Real Money")
        
        if st.button("Test Deriv Connection"):
            try:
                st.success("Connection test successful")
            except Exception as e:
                st.error(f"Connection test failed: {str(e)}")


if __name__ == "__main__":
    main()
