"""
SENTIENX Deriv OAuth Authentication Server
Handles Deriv OAuth 2.0 authentication flow via cloudflared tunnel
Port: 8502
"""

from flask import Flask, redirect, request, jsonify, session
from flask_cors import CORS
import os
import requests
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import urllib.parse

load_dotenv()

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv('SECRET_KEY', 'sentienx-oauth-secret-key-2025')

# Configuration
DERIV_CONFIG = {
    'app_id': os.getenv('DERIV_APP_ID', 'YOUR_DERIV_APP_ID'),
    'app_secret': os.getenv('DERIV_APP_SECRET', 'YOUR_DERIV_APP_SECRET'),
    'oauth_url': 'https://oauth.deriv.com/oauth2/authorize',
    'token_url': 'https://oauth.deriv.com/oauth2/token',
    'api_url': 'https://api.deriv.com/api/v3',
}

# Store for credentials (in production, use secure DB)
CREDENTIALS_FILE = Path(__file__).parent / '.deriv_credentials.json'

def load_credentials():
    """Load stored Deriv credentials"""
    if CREDENTIALS_FILE.exists():
        try:
            with open(CREDENTIALS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_credentials(creds):
    """Save Deriv credentials securely"""
    try:
        with open(CREDENTIALS_FILE, 'w') as f:
            json.dump(creds, f, indent=2)
        # Restrict file permissions
        os.chmod(str(CREDENTIALS_FILE), 0o600)
        return True
    except Exception as e:
        print(f"Error saving credentials: {e}")
        return False

@app.route('/')
def index():
    """Deriv OAuth login page"""
    callback_url = request.host_url.rstrip('/') + '/callback'
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>SENTIENX - Deriv OAuth Login</title>
        <style>
            * {{ margin: 0; padding: 0; }}
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 50%, #2d3561 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
            }}
            .container {{
                background: rgba(26, 31, 58, 0.95);
                backdrop-filter: blur(10px);
                padding: 50px;
                border-radius: 15px;
                max-width: 500px;
                width: 100%;
                border: 2px solid #00d4ff;
                box-shadow: 0 8px 32px rgba(0, 212, 255, 0.1);
                text-align: center;
            }}
            h1 {{
                color: #00d4ff;
                margin-bottom: 10px;
                font-size: 32px;
                letter-spacing: 2px;
                text-transform: uppercase;
            }}
            .subtitle {{
                color: #a0a0a0;
                font-size: 14px;
                margin-bottom: 40px;
                letter-spacing: 1px;
            }}
            .divider {{
                height: 2px;
                background: linear-gradient(90deg, transparent, #00d4ff, transparent);
                margin: 30px 0;
            }}
            .description {{
                color: #e0e0e0;
                margin-bottom: 30px;
                line-height: 1.6;
                font-size: 14px;
            }}
            .info-box {{
                background-color: rgba(0, 212, 255, 0.1);
                border-left: 3px solid #00d4ff;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 30px;
                font-size: 13px;
                color: #00d4ff;
                text-align: left;
            }}
            .button-group {{
                display: flex;
                gap: 10px;
                margin-bottom: 20px;
            }}
            .btn {{
                flex: 1;
                padding: 14px 30px;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
                cursor: pointer;
                text-transform: uppercase;
                letter-spacing: 1.5px;
                transition: all 0.3s ease;
                text-decoration: none;
                display: inline-block;
            }}
            .btn-primary {{
                background-color: #00d4ff;
                color: #0a0e27;
            }}
            .btn-primary:hover {{
                background-color: #00f7ff;
                box-shadow: 0 0 30px rgba(0, 212, 255, 0.6);
                transform: translateY(-2px);
            }}
            .btn-secondary {{
                background-color: #2d3561;
                color: #00d4ff;
                border: 1px solid #00d4ff;
            }}
            .btn-secondary:hover {{
                background-color: #00d4ff;
                color: #0a0e27;
            }}
            .status {{
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
                font-size: 13px;
            }}
            .status.success {{
                background-color: rgba(0, 212, 0, 0.2);
                color: #00d700;
                border-left: 3px solid #00d700;
            }}
            .status.error {{
                background-color: rgba(255, 68, 68, 0.2);
                color: #ff4444;
                border-left: 3px solid #ff4444;
            }}
            .footer {{
                color: #a0a0a0;
                font-size: 12px;
                margin-top: 30px;
                text-align: center;
            }}
            code {{
                background-color: #0f1429;
                padding: 2px 6px;
                border-radius: 4px;
                color: #00d4ff;
                font-family: 'Courier New', monospace;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>SENTIENX</h1>
            <div class="subtitle">Deriv OAuth Authentication</div>
            <div class="divider"></div>
            
            <div class="description">
                Connect your Deriv account to SENTIENX for live trading and account management.
            </div>
            
            <div class="info-box">
                <strong>🔒 Secure Connection:</strong><br>
                This page is accessed via a secure cloudflared tunnel. Your Deriv credentials are protected.
            </div>
            
            <div id="status"></div>
            
            <div class="button-group">
                <a href="/login" class="btn btn-primary">🔐 Login with Deriv</a>
                <a href="/status" class="btn btn-secondary">📊 Check Status</a>
            </div>
            
            <div class="footer">
                <p><strong>Callback URL:</strong> <code>{callback_url}</code></p>
                <p style="margin-top: 10px;">Keep this URL secure and add it to your Deriv app settings</p>
            </div>
        </div>
        
        <script>
            // Check if we just came back from OAuth
            const params = new URLSearchParams(window.location.search);
            if (params.has('success')) {{
                const statusDiv = document.getElementById('status');
                statusDiv.innerHTML = '<div class="status success">✓ Successfully authenticated! Redirecting to dashboard...</div>';
                setTimeout(() => {{
                    window.location.href = 'http://localhost:8501';
                }}, 2000);
            }}
            if (params.has('error')) {{
                const statusDiv = document.getElementById('status');
                const error = params.get('error');
                statusDiv.innerHTML = '<div class="status error">✗ Authentication failed: ' + error + '</div>';
            }}
        </script>
    </body>
    </html>
    """
    return html

@app.route('/login')
def login():
    """Redirect to Deriv OAuth login"""
    try:
        callback_url = request.host_url.rstrip('/') + '/callback'
        
        # Build OAuth URL
        oauth_params = {
            'app_id': DERIV_CONFIG['app_id'],
            'redirect_uri': callback_url,
            'response_type': 'code',
            'scope': 'read write'
        }
        
        oauth_url = f"{DERIV_CONFIG['oauth_url']}?" + urllib.parse.urlencode(oauth_params)
        
        return redirect(oauth_url)
    except Exception as e:
        return redirect(f"/?error={str(e)}")

@app.route('/callback')
def callback():
    """Handle Deriv OAuth callback"""
    try:
        code = request.args.get('code')
        if not code:
            error = request.args.get('error', 'No authorization code received')
            return redirect(f"/?error={error}")
        
        callback_url = request.host_url.rstrip('/') + '/callback'
        
        # Exchange code for token
        token_data = {
            'client_id': DERIV_CONFIG['app_id'],
            'client_secret': DERIV_CONFIG['app_secret'],
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': callback_url
        }
        
        response = requests.post(DERIV_CONFIG['token_url'], json=token_data)
        
        if response.status_code != 200:
            return redirect(f"/?error=Failed to get access token")
        
        token_response = response.json()
        access_token = token_response.get('access_token')
        
        if not access_token:
            return redirect(f"/?error=No access token in response")
        
        # Get user account info
        headers = {'Authorization': f'Bearer {access_token}'}
        account_response = requests.get(f"{DERIV_CONFIG['api_url']}/account", headers=headers)
        
        if account_response.status_code != 200:
            return redirect(f"/?error=Failed to fetch account info")
        
        account_data = account_response.json()
        
        # Save credentials
        credentials = {
            'access_token': access_token,
            'refresh_token': token_response.get('refresh_token'),
            'expires_in': token_response.get('expires_in'),
            'account_info': account_data,
            'authenticated_at': datetime.now().isoformat()
        }
        
        if save_credentials(credentials):
            # Also update .env for future use
            update_env_credentials(access_token)
            return redirect("/?success=true")
        else:
            return redirect("/?error=Failed to save credentials")
    
    except Exception as e:
        return redirect(f"/?error={str(e)}")

def update_env_credentials(token):
    """Update .env with new token"""
    try:
        env_path = Path(__file__).parent / '.env'
        
        content = ""
        if env_path.exists():
            with open(env_path, 'r') as f:
                lines = f.readlines()
            
            for line in lines:
                if not line.startswith('DERIV_API_TOKEN='):
                    content += line
        
        content += f"DERIV_API_TOKEN={token}\n"
        
        with open(env_path, 'w') as f:
            f.write(content)
        
        os.chmod(str(env_path), 0o600)
        return True
    except:
        return False

@app.route('/status')
def status():
    """Check authentication status"""
    try:
        creds = load_credentials()
        
        if not creds or 'access_token' not in creds:
            html = """
            <html>
            <head><style>
                body { font-family: Arial; background: #0a0e27; color: #e0e0e0; padding: 40px; }
                .card { background: #1a1f3a; padding: 30px; border-radius: 10px; border: 2px solid #00d4ff; max-width: 600px; margin: auto; }
                h1 { color: #00d4ff; }
                .status { background: rgba(255, 68, 68, 0.2); padding: 15px; border-radius: 8px; color: #ff4444; border-left: 3px solid #ff4444; }
                a { color: #00d4ff; text-decoration: none; }
            </style></head>
            <body>
                <div class="card">
                    <h1>Authentication Status</h1>
                    <div class="status">✗ Not Authenticated</div>
                    <p>No valid Deriv credentials found.</p>
                    <p><a href="/">← Go back to login</a></p>
                </div>
            </body>
            </html>
            """
            return html
        
        auth_time = creds.get('authenticated_at', 'Unknown')
        account_info = creds.get('account_info', {})
        
        html = f"""
        <html>
        <head><style>
            body {{ font-family: Arial; background: #0a0e27; color: #e0e0e0; padding: 40px; }}
            .card {{ background: #1a1f3a; padding: 30px; border-radius: 10px; border: 2px solid #00d4ff; max-width: 600px; margin: auto; }}
            h1 {{ color: #00d4ff; }}
            .status {{ background: rgba(0, 212, 0, 0.2); padding: 15px; border-radius: 8px; color: #00d700; border-left: 3px solid #00d700; margin-bottom: 20px; }}
            .info {{ background: #0f1429; padding: 15px; border-radius: 8px; margin: 15px 0; }}
            .info-item {{ margin: 10px 0; }}
            .label {{ color: #00d4ff; font-weight: bold; }}
            .value {{ color: #a0a0a0; }}
            a {{ color: #00d4ff; text-decoration: none; }}
            .button-group {{ display: flex; gap: 10px; margin-top: 20px; }}
            .btn {{ padding: 10px 20px; border: 1px solid #00d4ff; border-radius: 5px; cursor: pointer; }}
        </style></head>
        <body>
            <div class="card">
                <h1>Authentication Status</h1>
                <div class="status">✓ Successfully Authenticated</div>
                
                <div class="info">
                    <div class="info-item">
                        <span class="label">Authenticated at:</span>
                        <span class="value">{auth_time}</span>
                    </div>
                    <div class="info-item">
                        <span class="label">Token Status:</span>
                        <span class="value">Active</span>
                    </div>
                </div>
                
                <h3 style="color: #00d4ff; margin-top: 30px;">Account Information</h3>
                <div class="info">
                    <pre style="color: #00d4ff; overflow-x: auto; font-size: 12px;">
{json.dumps(account_info, indent=2)}
                    </pre>
                </div>
                
                <div class="button-group">
                    <a href="/" class="btn">← Back</a>
                    <a href="http://localhost:8501" class="btn">Go to Dashboard →</a>
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    except Exception as e:
        return f"<h1>Error</h1><p>{str(e)}</p>"

@app.route('/api/credentials')
def get_credentials_api():
    """API endpoint to get stored credentials"""
    try:
        creds = load_credentials()
        if creds and 'access_token' in creds:
            return jsonify({
                'authenticated': True,
                'token': creds['access_token'],
                'account_info': creds.get('account_info', {}),
                'authenticated_at': creds.get('authenticated_at')
            })
        else:
            return jsonify({'authenticated': False}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/logout')
def logout():
    """Clear stored credentials"""
    try:
        if CREDENTIALS_FILE.exists():
            CREDENTIALS_FILE.unlink()
        return jsonify({'success': True, 'message': 'Logged out successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    print("""
    ╔═══════════════════════════════════════════════════════╗
    ║   SENTIENX Deriv OAuth Server - Port 8502            ║
    ║                                                        ║
    ║   Access via cloudflared tunnel:                      ║
    ║   http://localhost:8502                               ║
    ║                                                        ║
    ║   Features:                                            ║
    ║   - Deriv OAuth 2.0 authentication                    ║
    ║   - Secure credential storage                         ║
    ║   - Automatic .env updates                            ║
    ║   - Status monitoring                                 ║
    ╚═══════════════════════════════════════════════════════╝
    """)
    
    app.run(
        host="0.0.0.0",
        port=8502,
        debug=False,
        use_reloader=False
    )
