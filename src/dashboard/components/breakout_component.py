"""
Breakout Analysis Dashboard Component
Displays breakout predictions and levels
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import json

def display_breakout_dashboard():
    """Main breakout analysis dashboard"""
    
    st.markdown("""
    <style>
        .breakout-section { 
            background: linear-gradient(135deg, #1a1f3a 0%, #16213e 100%);
            padding: 20px;
            border-radius: 10px;
            margin: 10px 0;
            border-left: 4px solid #00d4ff;
        }
        .target-box {
            background: rgba(0, 212, 255, 0.1);
            border: 1px solid #00d4ff;
            padding: 12px;
            border-radius: 8px;
            margin: 8px 0;
        }
        .support-box {
            background: rgba(255, 68, 68, 0.1);
            border: 1px solid #ff4444;
            padding: 12px;
            border-radius: 8px;
            margin: 8px 0;
        }
        .resistance-box {
            background: rgba(0, 212, 255, 0.1);
            border: 1px solid #00d4ff;
            padding: 12px;
            border-radius: 8px;
            margin: 8px 0;
        }
        .confidence-high { color: #00ff00; }
        .confidence-medium { color: #ffaa00; }
        .confidence-low { color: #ff4444; }
    </style>
    """, unsafe_allow_html=True)
    
    # Symbol selector
    col1, col2, col3 = st.columns(3)
    
    with col1:
        symbol = st.selectbox(
            "Select Symbol",
            ["EURUSD", "GBPUSD", "USDJPY"],
            key="breakout_symbol"
        )
    
    with col2:
        analysis_type = st.radio(
            "Analysis Type",
            ["Prediction", "Levels", "Active Breakout", "Summary"],
            horizontal=True
        )
    
    with col3:
        if st.button("🔄 Refresh Analysis", key="refresh_breakout"):
            st.rerun()
    
    # API base URL
    api_url = "http://localhost:5000"
    
    try:
        if analysis_type == "Prediction":
            display_prediction_analysis(api_url, symbol)
        elif analysis_type == "Levels":
            display_levels_analysis(api_url, symbol)
        elif analysis_type == "Active Breakout":
            display_active_breakout(api_url, symbol)
        else:
            display_summary_analysis(api_url, symbol)
    
    except Exception as e:
        st.error(f"Error loading breakout analysis: {str(e)}")

def display_prediction_analysis(api_url: str, symbol: str):
    """Display breakout prediction analysis"""
    
    st.markdown("### 🎯 Breakout Prediction", unsafe_allow_html=True)
    
    try:
        response = requests.get(f"{api_url}/api/breakout/predict/{symbol}", timeout=10)
        if response.status_code != 200:
            st.error("Could not load prediction data")
            return
        
        data = response.json()
        
        # Current price
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Current Price", f"${data['current_price']:.5f}")
        with col2:
            st.metric("Volatility", f"{data['volatility_score']:.1f}%")
        with col3:
            st.metric("Momentum", data['momentum_direction'])
        
        # Breakout targets
        st.markdown("#### Breakout Targets")
        
        if data['upside_breakout']:
            upside = data['upside_breakout']
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown(f"""
                <div class="target-box">
                    <strong>📈 Upside Target</strong><br>
                    Level: <strong>${upside['level']:.5f}</strong><br>
                    Strength: {upside['strength']:.1f}%<br>
                    Confidence: <span class="confidence-high">{upside['confidence']:.1f}%</span>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div class="target-box">
                    <strong>Time to Breakout</strong><br>
                    {upside['time_to_breakout']} candles<br>
                    Type: {upside['type']}
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                st.markdown(f"""
                <div class="target-box">
                    <strong>Probability (24h)</strong><br>
                    {data['probability_of_breakout']:.1f}%<br>
                    Direction: {upside['direction']}
                </div>
                """, unsafe_allow_html=True)
        
        if data['downside_breakout']:
            downside = data['downside_breakout']
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown(f"""
                <div class="support-box">
                    <strong>📉 Downside Target</strong><br>
                    Level: <strong>${downside['level']:.5f}</strong><br>
                    Strength: {downside['strength']:.1f}%<br>
                    Confidence: <span class="confidence-high">{downside['confidence']:.1f}%</span>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div class="support-box">
                    <strong>Time to Breakout</strong><br>
                    {downside['time_to_breakout']} candles<br>
                    Type: {downside['type']}
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                st.markdown(f"""
                <div class="support-box">
                    <strong>Probability (24h)</strong><br>
                    {data['probability_of_breakout']:.1f}%<br>
                    Direction: {downside['direction']}
                </div>
                """, unsafe_allow_html=True)
        
        # Trading levels
        st.markdown("#### Trading Levels")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Entry", f"${data['recommended_entry']:.5f}")
        with col2:
            st.metric("Stop Loss", f"${data['stop_loss']:.5f}")
        with col3:
            st.metric("TP 1", f"${data['take_profit_1']:.5f}")
        with col4:
            st.metric("TP 2", f"${data['take_profit_2']:.5f}")
        
        # Key levels
        st.markdown("#### Key Support & Resistance")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            <div class="resistance-box">
                <strong>Next Resistance</strong><br>
                ${data['next_resistance']:.5f}
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="support-box">
                <strong>Next Support</strong><br>
                ${data['next_support']:.5f}
            </div>
            """, unsafe_allow_html=True)
    
    except Exception as e:
        st.error(f"Error: {str(e)}")

def display_levels_analysis(api_url: str, symbol: str):
    """Display support and resistance levels"""
    
    st.markdown("### 📊 Support & Resistance Levels", unsafe_allow_html=True)
    
    try:
        response = requests.get(f"{api_url}/api/breakout/levels/{symbol}", timeout=10)
        if response.status_code != 200:
            st.error("Could not load levels data")
            return
        
        data = response.json()
        current = data['current_price']
        
        # Create visualization
        fig = go.Figure()
        
        # Resistance levels
        for i, level in enumerate(data['resistance_levels']):
            fig.add_hline(
                y=level,
                line_dash="dash",
                line_color="#00d4ff",
                annotation_text=f"R{i+1}: ${level:.5f}",
                annotation_position="right"
            )
        
        # Support levels
        for i, level in enumerate(data['support_levels']):
            fig.add_hline(
                y=level,
                line_dash="dash",
                line_color="#ff4444",
                annotation_text=f"S{i+1}: ${level:.5f}",
                annotation_position="right"
            )
        
        # Current price
        fig.add_hline(
            y=current,
            line_color="#ffaa00",
            line_width=2,
            annotation_text=f"Current: ${current:.5f}",
            annotation_position="right"
        )
        
        fig.update_layout(
            title=f"{symbol} - Support & Resistance Levels",
            yaxis_title="Price",
            template="plotly_dark",
            hovermode="x unified",
            height=500
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Levels table
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Resistance Levels**")
            df_res = pd.DataFrame({
                'Level': data['resistance_levels'],
                'Distance': [f"{((level/current - 1) * 100):.2f}%" for level in data['resistance_levels']]
            })
            st.dataframe(df_res, use_container_width=True)
        
        with col2:
            st.markdown("**Support Levels**")
            df_sup = pd.DataFrame({
                'Level': data['support_levels'],
                'Distance': [f"{((1 - level/current) * 100):.2f}%" for level in data['support_levels']]
            })
            st.dataframe(df_sup, use_container_width=True)
    
    except Exception as e:
        st.error(f"Error: {str(e)}")

def display_active_breakout(api_url: str, symbol: str):
    """Display active breakout detection"""
    
    st.markdown("### 🚀 Active Breakout Detection", unsafe_allow_html=True)
    
    try:
        response = requests.get(f"{api_url}/api/breakout/active/{symbol}", timeout=10)
        if response.status_code != 200:
            st.error("Could not load breakout data")
            return
        
        data = response.json()
        
        if data['active_breakout']:
            breakout_type = data['breakout_type']
            is_upside = 'UPSIDE' in breakout_type
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "Status",
                    "🟢 ACTIVE",
                    delta=f"{data['distance_percent']:.2f}%"
                )
            
            with col2:
                st.metric(
                    "Type",
                    "📈 Upside" if is_upside else "📉 Downside"
                )
            
            with col3:
                st.metric(
                    "Breakout Level",
                    f"${data['breakout_level']:.5f}"
                )
            
            with col4:
                st.metric(
                    "Strength",
                    f"{data['strength']:.1f}/100"
                )
            
            st.success(f"Active {breakout_type} detected! Price moved {data['distance_percent']:.2f}% beyond the level.")
        
        else:
            st.info("No active breakout currently detected")
    
    except Exception as e:
        st.error(f"Error: {str(e)}")

def display_summary_analysis(api_url: str, symbol: str):
    """Display complete breakout analysis summary"""
    
    st.markdown("### 📋 Breakout Analysis Summary", unsafe_allow_html=True)
    
    try:
        response = requests.get(f"{api_url}/api/breakout/summary/{symbol}", timeout=10)
        if response.status_code != 200:
            st.error("Could not load summary data")
            return
        
        data = response.json()
        
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Current Price", f"${data['current_price']:.5f}")
        with col2:
            st.metric("Volatility", f"{data['volatility']:.1f}%")
        with col3:
            st.metric("Momentum", data['momentum'])
        with col4:
            st.metric("Breakout Prob (24h)", f"{data['breakout_probability_24h']:.1f}%")
        
        st.divider()
        
        # Targets
        st.markdown("#### Price Targets")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"""
            <div class="resistance-box">
                <strong>📈 Upside Target</strong><br>
                ${data['upside_target']:.5f if data['upside_target'] else 'N/A'}
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="target-box">
                <strong>Resistance</strong><br>
                ${data['next_resistance']:.5f}
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="support-box">
                <strong>📉 Downside Target</strong><br>
                ${data['downside_target']:.5f if data['downside_target'] else 'N/A'}
            </div>
            """, unsafe_allow_html=True)
        
        st.divider()
        
        # Trading Plan
        st.markdown("#### Trading Plan")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"""
            <div class="target-box">
                <strong>Entry Point</strong><br>
                ${data['recommended_entry']:.5f}
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="support-box">
                <strong>Stop Loss</strong><br>
                ${data['stop_loss']:.5f}
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="resistance-box">
                <strong>Take Profits</strong><br>
                TP1: ${data['take_profit_1']:.5f}<br>
                TP2: ${data['take_profit_2']:.5f}
            </div>
            """, unsafe_allow_html=True)
        
        st.divider()
        
        # Active breakout status
        if data['active_breakout']:
            st.warning(f"⚠️ **Active Breakout**: {data['active_breakout'].get('type', 'Unknown')}")
        else:
            st.info("No active breakout detected")
    
    except Exception as e:
        st.error(f"Error: {str(e)}")
