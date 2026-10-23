"""
Process Manager for SENTIENX Bot
Handles starting/stopping bot processes and managing state
"""

import os
import subprocess
import json
import time
from pathlib import Path
from datetime import datetime
import psutil

STATE_FILE = Path(__file__).parent / ".bot_state.json"
PID_FILE = Path(__file__).parent / ".bot.pid"


def get_bot_state():
    """Get current bot state"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {
        'running': False,
        'started_at': None,
        'pid': None,
        'status': 'stopped',
        'last_error': None
    }


def save_bot_state(state):
    """Save bot state"""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def is_bot_running():
    """Check if bot process is running"""
    state = get_bot_state()
    
    if state.get('pid'):
        try:
            process = psutil.Process(state['pid'])
            return process.is_running()
        except:
            pass
    
    return False


def start_bot():
    """Start the bot process"""
    try:
        if is_bot_running():
            return {
                'success': False,
                'message': 'Bot is already running',
                'running': True
            }
        
        # Start trading bot in background
        base_dir = Path(__file__).parent
        bot_script = base_dir / "sentienx.py"
        
        process = subprocess.Popen(
            ['python3', str(bot_script), '--mode', 'trading'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(base_dir)
        )
        
        state = {
            'running': True,
            'started_at': datetime.now().isoformat(),
            'pid': process.pid,
            'status': 'running',
            'last_error': None
        }
        save_bot_state(state)
        
        # Save PID
        with open(PID_FILE, 'w') as f:
            f.write(str(process.pid))
        
        return {
            'success': True,
            'message': f'Bot started successfully (PID: {process.pid})',
            'running': True,
            'pid': process.pid
        }
    except Exception as e:
        error_msg = str(e)
        state = {
            'running': False,
            'started_at': None,
            'pid': None,
            'status': 'error',
            'last_error': error_msg
        }
        save_bot_state(state)
        
        return {
            'success': False,
            'message': f'Failed to start bot: {error_msg}',
            'running': False,
            'error': error_msg
        }


def stop_bot():
    """Stop the bot process"""
    try:
        state = get_bot_state()
        pid = state.get('pid')
        
        if not pid:
            return {
                'success': False,
                'message': 'No bot process to stop',
                'running': False
            }
        
        try:
            process = psutil.Process(pid)
            process.terminate()
            
            # Wait for process to terminate
            try:
                process.wait(timeout=5)
            except psutil.TimeoutExpired:
                process.kill()
        except psutil.NoSuchProcess:
            pass
        
        # Update state
        state = {
            'running': False,
            'started_at': None,
            'pid': None,
            'status': 'stopped',
            'last_error': None
        }
        save_bot_state(state)
        
        # Remove PID file
        if PID_FILE.exists():
            PID_FILE.unlink()
        
        return {
            'success': True,
            'message': 'Bot stopped successfully',
            'running': False
        }
    except Exception as e:
        return {
            'success': False,
            'message': f'Failed to stop bot: {str(e)}',
            'running': is_bot_running(),
            'error': str(e)
        }


def get_bot_status():
    """Get detailed bot status"""
    state = get_bot_state()
    running = is_bot_running()
    
    status_info = {
        'running': running,
        'pid': state.get('pid'),
        'status': state.get('status'),
        'started_at': state.get('started_at'),
        'last_error': state.get('last_error'),
        'uptime': None
    }
    
    if running and state.get('started_at'):
        try:
            start_time = datetime.fromisoformat(state['started_at'])
            uptime = datetime.now() - start_time
            status_info['uptime'] = str(uptime).split('.')[0]
        except:
            pass
    
    return status_info
