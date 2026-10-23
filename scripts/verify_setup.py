#!/usr/bin/env python3
"""
SENTIENX Setup Verification Script
Checks if everything is properly configured for trading
"""

import sys
import os
from pathlib import Path

def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")

def check_file(path, required=True):
    exists = Path(path).exists()
    status = "OK" if exists else "MISSING"
    symbol = "✓" if exists else "✗"
    print(f"  {symbol} {path}: {status}")
    return exists

def check_import(module_name):
    try:
        __import__(module_name)
        print(f"  ✓ {module_name}: OK")
        return True
    except ImportError:
        print(f"  ✗ {module_name}: MISSING")
        return False

def main():
    print_header("SENTIENX Setup Verification")
    
    # Check Python version
    print("Python Version:")
    version = sys.version.split()[0]
    print(f"  {version}")
    if sys.version_info >= (3, 8):
        print("  ✓ Compatible\n")
    else:
        print("  ✗ Python 3.8+ required\n")
        return False
    
    # Check required files
    print_header("Required Files")
    
    files_ok = True
    files_ok &= check_file("config.py")
    files_ok &= check_file("trading_bot.py")
    files_ok &= check_file("dashboard/app.py")
    files_ok &= check_file("api/services/deriv_service.py")
    files_ok &= check_file(".env")
    print()
    
    # Check required directories
    print_header("Required Directories")
    
    dirs_ok = True
    dirs_ok &= check_file("logs", required=False)
    dirs_ok &= check_file("data", required=False)
    dirs_ok &= check_file("models", required=False)
    print()
    
    # Check Python dependencies
    print_header("Python Dependencies")
    
    deps_ok = True
    deps_ok &= check_import("streamlit")
    deps_ok &= check_import("pandas")
    deps_ok &= check_import("numpy")
    deps_ok &= check_import("plotly")
    deps_ok &= check_import("requests")
    print()
    
    # Check Deriv configuration
    print_header("Deriv Configuration")
    
    try:
        from config import DERIV_CONFIG
        
        if DERIV_CONFIG.get('app_id') == 'YOUR_DERIV_APP_ID':
            print("  ✗ DERIV_APP_ID not configured")
            deriv_ok = False
        else:
            print("  ✓ DERIV_APP_ID configured")
            deriv_ok = True
        
        if DERIV_CONFIG.get('api_token') == 'YOUR_DERIV_API_TOKEN':
            print("  ✗ DERIV_API_TOKEN not configured")
            deriv_ok = False
        else:
            print("  ✓ DERIV_API_TOKEN configured")
        
        print(f"  Environment: {DERIV_CONFIG.get('environment', 'unknown')}")
        print()
    except Exception as e:
        print(f"  ✗ Error loading config: {str(e)}")
        deriv_ok = False
        print()
    
    # Check trading configuration
    print_header("Trading Configuration")
    
    try:
        from config import TRADING_CONFIG, RISK_CONFIG
        
        print(f"  Symbols: {TRADING_CONFIG.get('symbols', [])}")
        print(f"  Auto Trading: {TRADING_CONFIG.get('auto_trading', False)}")
        print(f"  Confidence Threshold: {TRADING_CONFIG.get('confidence_threshold', 0.7)}")
        print(f"  Max Risk per Trade: {RISK_CONFIG.get('max_risk_per_trade', 0.01)}")
        print(f"  Max Daily Loss: ${RISK_CONFIG.get('max_daily_loss', 10)}")
        print(f"  Max Open Positions: {RISK_CONFIG.get('max_open_positions', 3)}")
        print()
    except Exception as e:
        print(f"  ✗ Error loading config: {str(e)}")
        print()
    
    # Test Deriv connection
    print_header("Deriv Connection Test")
    
    try:
        from api.services.deriv_service import DerivService
        from config import DERIV_CONFIG
        
        print("  Attempting connection to Deriv...")
        
        deriv = DerivService(
            app_id=DERIV_CONFIG.get('app_id'),
            api_token=DERIV_CONFIG.get('api_token'),
            environment=DERIV_CONFIG.get('environment', 'real')
        )
        
        if deriv.connect():
            print("  ✓ Successfully connected to Deriv")
            
            balance = deriv.get_account_balance()
            if balance:
                print(f"  ✓ Account Balance: ${balance.get('balance', 0):.2f}")
                print(f"  ✓ Currency: {balance.get('currency', 'USD')}")
            
            deriv.disconnect()
        else:
            print("  ✗ Failed to connect to Deriv")
            print("  Check credentials in .env file")
        print()
    except Exception as e:
        print(f"  ✗ Connection error: {str(e)}")
        print()
    
    # Summary
    print_header("Verification Summary")
    
    all_ok = files_ok and deps_ok and deriv_ok
    
    if all_ok:
        print("  ✓ All checks passed!")
        print("\n  Ready to start trading bot:")
        print("    bash start_bot.sh")
        return True
    else:
        print("  ✗ Some checks failed")
        print("\n  To fix:")
        if not files_ok:
            print("    - Check required files exist")
        if not deps_ok:
            print("    - Run: pip install -r requirements.txt")
        if not deriv_ok:
            print("    - Update Deriv credentials in .env")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
