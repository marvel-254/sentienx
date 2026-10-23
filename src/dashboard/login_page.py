"""
Redesigned Login Page - Clean, Modern, Professional
Main entry point for SENTIENX
"""

import streamlit as st
from datetime import datetime
import time
import sys
from pathlib import Path

# Set page config first
st.set_page_config(
    page_title="SENTIENX Login",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="collapsed"
)
    
    # Modern, minimal styling
    st.markdown("""
    <style>
    * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }
    
    html, body, [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f4c75 100%);
        background-attachment: fixed;
        min-height: 100vh;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    [data-testid="stSidebar"] {
        display: none;
    }
    
    .block-container {
        padding: 0;
        max-width: 100%;
    }
    
    .login-container {
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 100vh;
        width: 100%;
    }
    
    .login-card {
        background: rgba(15, 23, 42, 0.95);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(100, 200, 255, 0.2);
        border-radius: 20px;
        padding: 60px 50px;
        width: 100%;
        max-width: 450px;
        box-shadow: 0 25px 50px rgba(0, 0, 0, 0.3);
    }
    
    .login-header {
        text-align: center;
        margin-bottom: 40px;
    }
    
    .login-logo {
        font-size: 48px;
        margin-bottom: 15px;
        animation: float 3s ease-in-out infinite;
    }
    
    .login-title {
        font-size: 32px;
        font-weight: 700;
        color: #ffffff;
        margin-bottom: 8px;
        background: linear-gradient(135deg, #64c8ff 0%, #00d4ff 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    .login-subtitle {
        font-size: 14px;
        color: #94a3b8;
        margin-bottom: 8px;
    }
    
    .login-badge {
        display: inline-block;
        background: rgba(0, 212, 255, 0.1);
        border: 1px solid rgba(0, 212, 255, 0.3);
        color: #64c8ff;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        margin-top: 12px;
    }
    
    .login-form {
        margin-bottom: 30px;
    }
    
    .form-group {
        margin-bottom: 20px;
    }
    
    .form-label {
        display: block;
        font-size: 14px;
        font-weight: 600;
        color: #cbd5e1;
        margin-bottom: 8px;
    }
    
    .form-input {
        width: 100%;
        padding: 12px 16px;
        background: rgba(30, 41, 59, 0.8);
        border: 1.5px solid rgba(100, 200, 255, 0.2);
        border-radius: 10px;
        color: #ffffff;
        font-size: 14px;
        transition: all 0.3s ease;
    }
    
    .form-input:focus {
        outline: none;
        border-color: rgba(0, 212, 255, 0.5);
        background: rgba(30, 41, 59, 1);
        box-shadow: 0 0 0 3px rgba(0, 212, 255, 0.1);
    }
    
    .form-input::placeholder {
        color: #64748b;
    }
    
    .remember-forgot {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 30px;
        font-size: 13px;
    }
    
    .remember-me {
        display: flex;
        align-items: center;
        gap: 6px;
        color: #94a3b8;
        cursor: pointer;
    }
    
    .forgot-password {
        color: #64c8ff;
        text-decoration: none;
        transition: color 0.3s ease;
    }
    
    .forgot-password:hover {
        color: #00d4ff;
    }
    
    .login-button {
        width: 100%;
        padding: 13px 20px;
        background: linear-gradient(135deg, #0d99ff 0%, #00d4ff 100%);
        border: none;
        border-radius: 10px;
        color: white;
        font-size: 15px;
        font-weight: 700;
        cursor: pointer;
        transition: all 0.3s ease;
        margin-bottom: 15px;
    }
    
    .login-button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 25px rgba(0, 212, 255, 0.3);
    }
    
    .login-button:active {
        transform: translateY(0);
    }
    
    .divider {
        display: flex;
        align-items: center;
        margin: 30px 0;
        color: #64748b;
        font-size: 13px;
    }
    
    .divider-line {
        flex: 1;
        height: 1px;
        background: rgba(100, 200, 255, 0.1);
    }
    
    .divider-text {
        margin: 0 15px;
    }
    
    .social-logins {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
        margin-bottom: 25px;
    }
    
    .social-button {
        padding: 11px 16px;
        background: rgba(30, 41, 59, 0.8);
        border: 1.5px solid rgba(100, 200, 255, 0.15);
        border-radius: 10px;
        color: #cbd5e1;
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    
    .social-button:hover {
        border-color: rgba(0, 212, 255, 0.4);
        background: rgba(30, 41, 59, 1);
        color: #64c8ff;
    }
    
    .signup-link {
        text-align: center;
        font-size: 14px;
        color: #94a3b8;
    }
    
    .signup-link a {
        color: #00d4ff;
        text-decoration: none;
        font-weight: 600;
        transition: color 0.3s ease;
    }
    
    .signup-link a:hover {
        color: #64c8ff;
    }
    
    .features-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 20px;
        margin-top: 50px;
        margin-left: 50px;
    }
    
    .feature-card {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(100, 200, 255, 0.1);
        border-radius: 12px;
        padding: 20px;
        transition: all 0.3s ease;
    }
    
    .feature-card:hover {
        border-color: rgba(0, 212, 255, 0.3);
        background: rgba(30, 41, 59, 0.8);
    }
    
    .feature-icon {
        font-size: 24px;
        margin-bottom: 10px;
    }
    
    .feature-title {
        font-size: 14px;
        font-weight: 600;
        color: #cbd5e1;
        margin-bottom: 5px;
    }
    
    .feature-text {
        font-size: 12px;
        color: #94a3b8;
    }
    
    @keyframes float {
        0%, 100% { transform: translateY(0px); }
        50% { transform: translateY(-15px); }
    }
    
    @keyframes slideIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .login-card {
        animation: slideIn 0.6s ease-out;
    }
    
    </style>
    """, unsafe_allow_html=True)
    
    # Main layout
    col1, col2, col3 = st.columns([1, 1.2, 1])
    
    with col1:
        st.write("")  # Spacer
    
    with col2:
        # Login Card
        st.markdown("""
        <div class="login-container">
            <div class="login-card">
        """, unsafe_allow_html=True)
        
        # Header
        st.markdown("""
        <div class="login-header">
            <div class="login-logo">🚀</div>
            <div class="login-title">SENTIENX</div>
            <div class="login-subtitle">AI-Powered Trading System</div>
            <div class="login-badge">Live Trading Mode</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Form
        st.markdown('<div class="login-form">', unsafe_allow_html=True)
        
        # Email/Username
        st.markdown('<div class="form-group">', unsafe_allow_html=True)
        st.markdown('<label class="form-label">Email or Username</label>', unsafe_allow_html=True)
        email = st.text_input(
            "Email",
            placeholder="user@example.com",
            label_visibility="collapsed",
            key="email"
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Password
        st.markdown('<div class="form-group">', unsafe_allow_html=True)
        st.markdown('<label class="form-label">Password</label>', unsafe_allow_html=True)
        password = st.text_input(
            "Password",
            placeholder="••••••••",
            type="password",
            label_visibility="collapsed",
            key="password"
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Remember & Forgot
        col_rem, col_forg = st.columns(2)
        with col_rem:
            st.markdown('<div class="remember-me"><input type="checkbox"> Remember me</div>', unsafe_allow_html=True)
        with col_forg:
            st.markdown('<a href="#" class="forgot-password">Forgot password?</a>', unsafe_allow_html=True)
        
        st.write("")
        
        # Login Button
        if st.button("Sign In", use_container_width=True, key="login_btn"):
            if email and password:
                st.success("✅ Login successful! Redirecting to dashboard...")
                time.sleep(1)
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Please enter email and password")
        
        st.write("")
        
        # Divider
        st.markdown("""
        <div class="divider">
            <div class="divider-line"></div>
            <div class="divider-text">or continue with</div>
            <div class="divider-line"></div>
        </div>
        """, unsafe_allow_html=True)
        
        # Social buttons
        col_google, col_deriv = st.columns(2)
        with col_google:
            if st.button("🔍 Google", use_container_width=True, key="google_btn"):
                st.info("Google login coming soon...")
        
        with col_deriv:
            if st.button("📊 Deriv", use_container_width=True, key="deriv_btn"):
                st.info("Deriv OAuth redirecting...")
        
        st.write("")
        
        # Sign up link
        st.markdown("""
        <div class="signup-link">
            Don't have an account? <a href="#">Create one</a>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown('</div></div>', unsafe_allow_html=True)
    
    with col3:
        # Features sidebar
        st.write("")
        st.write("")
        
        st.markdown("""
        <div class="features-grid">
            <div class="feature-card">
                <div class="feature-icon">📈</div>
                <div class="feature-title">Live Trading</div>
                <div class="feature-text">Real-time market analysis</div>
            </div>
            <div class="feature-card">
                <div class="feature-icon">🤖</div>
                <div class="feature-title">AI Predictions</div>
                <div class="feature-text">Breakout forecasting</div>
            </div>
            <div class="feature-card">
                <div class="feature-icon">📊</div>
                <div class="feature-title">Smart Analytics</div>
                <div class="feature-text">Advanced metrics</div>
            </div>
            <div class="feature-card">
                <div class="feature-icon">🔐</div>
                <div class="feature-title">Secure</div>
                <div class="feature-text">Enterprise security</div>
            </div>
        </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    render_login_page()
