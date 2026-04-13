#!/usr/bin/env python3
"""
Codex OAuth Browser Login Script

Automatically opens browser and captures OAuth tokens via local callback server.
Based on opencode-openai-codex-auth implementation.

Usage:
    python browser_login.py           # Browser OAuth (auto)
    python browser_login.py --device  # Device code flow (manual)
    python browser_login.py --refresh # Refresh existing token
"""

import os
import sys
import json
import time
import base64
import hashlib
import secrets
import webbrowser
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import httpx
except ImportError:
    print("Please install httpx: pip install httpx")
    sys.exit(1)

# ============================================================================
# Configuration (from openai/codex and opencode-openai-codex-auth)
# ============================================================================

CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"
CALLBACK_PORT = 1455
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}/auth/callback"
SCOPE = "openid profile email offline_access"

CODEX_HOME = Path.home() / ".codex"
AUTH_FILE = CODEX_HOME / "auth.json"

# Timeout for OAuth flow (seconds)
OAUTH_TIMEOUT = 300  # 5 minutes


class PKCEGenerator:
    """Generate PKCE code verifier and challenge."""
    
    @staticmethod
    def generate() -> tuple:
        """Generate PKCE verifier and challenge pair."""
        # Generate random verifier (43-128 chars)
        verifier = secrets.token_urlsafe(64)[:86]
        
        # Create S256 challenge
        digest = hashlib.sha256(verifier.encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).decode().rstrip('=')
        
        return verifier, challenge


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler to capture OAuth callback."""
    
    # Class variables to store result
    auth_code: Optional[str] = None
    auth_state: Optional[str] = None
    expected_state: Optional[str] = None
    
    def log_message(self, format, *args):
        # Suppress HTTP logs
        pass
    
    def do_GET(self):
        parsed = urlparse(self.path)
        
        if parsed.path != "/auth/callback":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return
        
        params = parse_qs(parsed.query)
        code = params.get('code', [None])[0]
        state = params.get('state', [None])[0]
        
        # Validate state
        if state != OAuthCallbackHandler.expected_state:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"State mismatch - possible CSRF attack")
            return
        
        if not code:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing authorization code")
            return
        
        # Store auth code
        OAuthCallbackHandler.auth_code = code
        OAuthCallbackHandler.auth_state = state
        
        # Send success page
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        
        success_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Codex OAuth - Success</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }
                .container {
                    text-align: center;
                    background: white;
                    padding: 40px 60px;
                    border-radius: 16px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                }
                .success-icon {
                    font-size: 64px;
                    margin-bottom: 20px;
                }
                h1 { color: #333; margin: 0 0 10px 0; }
                p { color: #666; margin: 0; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success-icon">✅</div>
                <h1>Authentication Successful!</h1>
                <p>You can close this window and return to your terminal.</p>
            </div>
        </body>
        </html>
        """
        self.wfile.write(success_html.encode())


def start_callback_server(state: str) -> HTTPServer:
    """Start local HTTP server for OAuth callback."""
    OAuthCallbackHandler.expected_state = state
    OAuthCallbackHandler.auth_code = None
    
    server = HTTPServer(('127.0.0.1', CALLBACK_PORT), OAuthCallbackHandler)
    server.timeout = 1
    return server


def build_authorization_url(verifier: str, challenge: str, state: str) -> str:
    """Build OAuth authorization URL with PKCE."""
    params = {
        'response_type': 'code',
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'scope': SCOPE,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
        'state': state,
        'id_token_add_organizations': 'true',
        'codex_cli_simplified_flow': 'true',
        'originator': 'codex_cli_rs',
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code_for_tokens(code: str, verifier: str) -> Dict[str, Any]:
    """Exchange authorization code for tokens."""
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            TOKEN_URL,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data={
                'grant_type': 'authorization_code',
                'client_id': CLIENT_ID,
                'code': code,
                'code_verifier': verifier,
                'redirect_uri': REDIRECT_URI,
            }
        )
        
        if resp.status_code != 200:
            raise Exception(f"Token exchange failed: {resp.status_code} - {resp.text}")
        
        return resp.json()


def refresh_token(refresh_token_value: str) -> Dict[str, Any]:
    """Refresh access token."""
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            TOKEN_URL,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data={
                'grant_type': 'refresh_token',
                'client_id': CLIENT_ID,
                'refresh_token': refresh_token_value,
            }
        )
        
        if resp.status_code != 200:
            raise Exception(f"Token refresh failed: {resp.status_code} - {resp.text}")
        
        return resp.json()


def save_tokens(tokens: Dict[str, Any]):
    """Save tokens to auth.json."""
    CODEX_HOME.mkdir(parents=True, exist_ok=True)
    
    auth_data = {
        "chatgpt": {
            "access_token": tokens.get("access_token", ""),
            "refresh_token": tokens.get("refresh_token", ""),
            "id_token": tokens.get("id_token", ""),
        },
        "last_refresh": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    
    with open(AUTH_FILE, 'w', encoding='utf-8') as f:
        json.dump(auth_data, f, indent=2)
    
    try:
        os.chmod(AUTH_FILE, 0o600)
    except Exception:
        pass
    
    print(f"\n💾 Tokens saved to: {AUTH_FILE}")


def run_browser_oauth():
    """Run browser-based OAuth flow."""
    print("=" * 60)
    print("  Codex OAuth - Browser Login")
    print("=" * 60)
    
    # Generate PKCE and state
    verifier, challenge = PKCEGenerator.generate()
    state = secrets.token_hex(16)
    
    # Build authorization URL
    auth_url = build_authorization_url(verifier, challenge, state)
    
    # Start callback server
    print("\n📡 Starting callback server on port", CALLBACK_PORT)
    try:
        server = start_callback_server(state)
    except OSError as e:
        print(f"\n❌ Failed to start callback server: {e}")
        print(f"   Port {CALLBACK_PORT} may be in use.")
        return
    
    # Open browser
    print("🌐 Opening browser...")
    print(f"\n   If browser doesn't open, visit:")
    print(f"   {auth_url[:80]}...")
    
    webbrowser.open(auth_url)
    
    # Wait for callback
    print("\n⏳ Waiting for authorization (timeout: 5 minutes)...")
    
    start_time = time.time()
    while time.time() - start_time < OAUTH_TIMEOUT:
        server.handle_request()
        
        if OAuthCallbackHandler.auth_code:
            break
        
        remaining = int(OAUTH_TIMEOUT - (time.time() - start_time))
        print(f"\r   Waiting... ({remaining}s remaining)  ", end="", flush=True)
    
    server.server_close()
    
    if not OAuthCallbackHandler.auth_code:
        print("\n\n❌ Authorization timed out")
        return
    
    # Exchange code for tokens
    print("\n\n🔄 Exchanging authorization code for tokens...")
    
    try:
        tokens = exchange_code_for_tokens(OAuthCallbackHandler.auth_code, verifier)
        save_tokens(tokens)
        
        print("\n✅ Login successful!")
        access_token = tokens.get('access_token', '')
        print(f"   Access token: {access_token[:50]}...")
        print("\n🎉 You can now use codex_oauth_module!")
        
    except Exception as e:
        print(f"\n❌ Token exchange failed: {e}")


def run_token_refresh():
    """Refresh existing tokens."""
    if not AUTH_FILE.exists():
        print(f"❌ Auth file not found: {AUTH_FILE}")
        return
    
    with open(AUTH_FILE, 'r') as f:
        auth_data = json.load(f)
    
    # Support different formats
    if "chatgpt" in auth_data:
        tokens = auth_data["chatgpt"]
    elif "tokens" in auth_data:
        tokens = auth_data["tokens"]
    else:
        tokens = auth_data
    
    refresh_token_value = tokens.get("refresh_token")
    
    if not refresh_token_value:
        print("❌ No refresh token found")
        return
    
    print("🔄 Refreshing token...")
    
    try:
        new_tokens = refresh_token(refresh_token_value)
        save_tokens(new_tokens)
        print("\n✅ Token refreshed successfully!")
    except Exception as e:
        print(f"\n❌ Refresh failed: {e}")
        print("   You may need to login again.")


def main():
    if "--device" in sys.argv:
        # Import and run device code flow
        try:
            from device_login import run_device_code_login
            run_device_code_login()
        except ImportError:
            print("Device login module not found. Please use browser login.")
    elif "--refresh" in sys.argv:
        run_token_refresh()
    else:
        run_browser_oauth()


if __name__ == "__main__":
    main()
