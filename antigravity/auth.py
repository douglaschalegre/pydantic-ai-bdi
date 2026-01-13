"""
OAuth authentication for Antigravity API.

Implements Google OAuth 2.0 with PKCE flow for authenticating with the
Antigravity Unified Gateway API.
"""

import asyncio
import base64
import hashlib
import json
import os
import secrets
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from threading import Thread
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from .constants import (
    ANTIGRAVITY_CLIENT_ID,
    ANTIGRAVITY_CLIENT_SECRET,
    ANTIGRAVITY_ENDPOINT_FALLBACKS,
    ANTIGRAVITY_HEADERS,
    ANTIGRAVITY_REDIRECT_URI,
    ANTIGRAVITY_SCOPES,
    ANTIGRAVITY_DEFAULT_PROJECT_ID,
    OAUTH_CALLBACK_PORT,
    TOKEN_STORAGE_PATH,
)


@dataclass
class TokenData:
    """Stored OAuth token data."""

    access_token: str
    refresh_token: str
    expires_at: float  # Unix timestamp
    email: str | None = None
    project_id: str | None = None


@dataclass
class PKCEPair:
    """PKCE code verifier and challenge pair."""

    verifier: str
    challenge: str


def generate_pkce() -> PKCEPair:
    """Generate a PKCE code verifier and challenge."""
    # Generate a random 32-byte verifier
    verifier = secrets.token_urlsafe(32)

    # Create SHA256 hash of verifier
    digest = hashlib.sha256(verifier.encode()).digest()

    # Base64url encode the hash
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()

    return PKCEPair(verifier=verifier, challenge=challenge)


def get_token_storage_path() -> Path:
    """Get the path to the token storage file."""
    return Path(os.path.expanduser(TOKEN_STORAGE_PATH))


def load_stored_tokens() -> TokenData | None:
    """Load stored tokens from disk."""
    path = get_token_storage_path()
    if not path.exists():
        return None

    try:
        with open(path, "r") as f:
            data = json.load(f)
        return TokenData(
            access_token=data.get("access_token", ""),
            refresh_token=data["refresh_token"],
            expires_at=data.get("expires_at", 0),
            email=data.get("email"),
            project_id=data.get("project_id"),
        )
    except (json.JSONDecodeError, KeyError, FileNotFoundError):
        return None


def save_tokens(tokens: TokenData) -> None:
    """Save tokens to disk."""
    path = get_token_storage_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "expires_at": tokens.expires_at,
        "email": tokens.email,
        "project_id": tokens.project_id,
    }

    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    # Set restrictive permissions (owner read/write only)
    os.chmod(path, 0o600)


def is_token_expired(tokens: TokenData, buffer_seconds: int = 300) -> bool:
    """Check if the access token is expired or will expire soon."""
    now = datetime.now(timezone.utc).timestamp()
    return now >= (tokens.expires_at - buffer_seconds)


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback."""

    code: str | None = None
    state: str | None = None
    error: str | None = None

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress HTTP server logs."""
        pass

    def do_GET(self) -> None:
        """Handle GET request from OAuth callback."""
        parsed = urlparse(self.path)

        if parsed.path == "/oauth-callback":
            query = parse_qs(parsed.query)

            # Check for error
            if "error" in query:
                OAuthCallbackHandler.error = query["error"][0]
                self._send_response("Authentication failed. You can close this window.")
                return

            # Extract code and state
            OAuthCallbackHandler.code = query.get("code", [None])[0]
            OAuthCallbackHandler.state = query.get("state", [None])[0]

            if OAuthCallbackHandler.code:
                self._send_response(
                    "Authentication successful! You can close this window and return to the terminal."
                )
            else:
                OAuthCallbackHandler.error = "No authorization code received"
                self._send_response("Authentication failed: No code received.")
        else:
            self.send_error(404)

    def _send_response(self, message: str) -> None:
        """Send an HTML response."""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Antigravity Authentication</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee;
        }}
        .container {{
            text-align: center;
            padding: 40px;
            background: rgba(255,255,255,0.1);
            border-radius: 16px;
            backdrop-filter: blur(10px);
        }}
        h1 {{ margin-bottom: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Antigravity Auth</h1>
        <p>{message}</p>
    </div>
</body>
</html>"""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())


def encode_state(verifier: str, project_id: str = "") -> str:
    """Encode PKCE verifier and project ID into OAuth state parameter."""
    payload = {"verifier": verifier, "projectId": project_id}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def decode_state(state: str) -> tuple[str, str]:
    """Decode OAuth state parameter back to verifier and project ID."""
    # Handle base64url padding
    normalized = state.replace("-", "+").replace("_", "/")
    padded = normalized + "=" * ((4 - len(normalized) % 4) % 4)
    payload = json.loads(base64.b64decode(padded).decode())
    return payload["verifier"], payload.get("projectId", "")


def build_authorization_url(pkce: PKCEPair, project_id: str = "") -> str:
    """Build the Google OAuth authorization URL."""
    params = {
        "client_id": ANTIGRAVITY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": ANTIGRAVITY_REDIRECT_URI,
        "scope": " ".join(ANTIGRAVITY_SCOPES),
        "code_challenge": pkce.challenge,
        "code_challenge_method": "S256",
        "state": encode_state(pkce.verifier, project_id),
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


async def exchange_code_for_tokens(
    code: str, verifier: str
) -> tuple[str, str, int, str | None]:
    """
    Exchange authorization code for access and refresh tokens.

    Returns: (access_token, refresh_token, expires_in, email)
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": ANTIGRAVITY_CLIENT_ID,
                "client_secret": ANTIGRAVITY_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": ANTIGRAVITY_REDIRECT_URI,
                "code_verifier": verifier,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if response.status_code != 200:
            raise Exception(f"Token exchange failed: {response.text}")

        data = response.json()
        access_token = data["access_token"]
        refresh_token = data["refresh_token"]
        expires_in = data.get("expires_in", 3600)

        # Fetch user info
        email = None
        try:
            user_response = await client.get(
                "https://www.googleapis.com/oauth2/v1/userinfo?alt=json",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if user_response.status_code == 200:
                email = user_response.json().get("email")
        except Exception:
            pass

        return access_token, refresh_token, expires_in, email


async def refresh_access_token(refresh_token: str) -> tuple[str, int]:
    """
    Refresh an access token using the refresh token.

    Returns: (access_token, expires_in)
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": ANTIGRAVITY_CLIENT_ID,
                "client_secret": ANTIGRAVITY_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            error_code = error_data.get("error", "unknown")
            if error_code == "invalid_grant":
                raise Exception(
                    "Refresh token is invalid or revoked. Please re-authenticate."
                )
            raise Exception(f"Token refresh failed: {response.text}")

        data = response.json()
        return data["access_token"], data.get("expires_in", 3600)


async def fetch_project_id(access_token: str) -> str | None:
    """
    Fetch the Antigravity project ID using the loadCodeAssist endpoint.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "google-api-nodejs-client/9.15.1",
        "X-Goog-Api-Client": "google-cloud-sdk vscode_cloudshelleditor/0.1",
        "Client-Metadata": ANTIGRAVITY_HEADERS["Client-Metadata"],
    }

    body = {
        "metadata": {
            "ideType": "IDE_UNSPECIFIED",
            "platform": "PLATFORM_UNSPECIFIED",
            "pluginType": "GEMINI",
        }
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        for endpoint in ANTIGRAVITY_ENDPOINT_FALLBACKS:
            try:
                url = f"{endpoint}/v1internal:loadCodeAssist"
                response = await client.post(url, json=body, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    # Try to extract project ID from response
                    project = data.get("cloudaicompanionProject")
                    if isinstance(project, str) and project:
                        return project
                    if isinstance(project, dict) and project.get("id"):
                        return project["id"]
            except Exception:
                continue

    return None


def run_oauth_server(timeout: int = 120) -> tuple[str | None, str | None, str | None]:
    """
    Run a local HTTP server to capture the OAuth callback.

    Returns: (code, state, error)
    """
    # Reset class variables
    OAuthCallbackHandler.code = None
    OAuthCallbackHandler.state = None
    OAuthCallbackHandler.error = None

    server = HTTPServer(("localhost", OAUTH_CALLBACK_PORT), OAuthCallbackHandler)
    server.timeout = timeout

    # Handle one request
    server.handle_request()
    server.server_close()

    return (
        OAuthCallbackHandler.code,
        OAuthCallbackHandler.state,
        OAuthCallbackHandler.error,
    )


async def interactive_oauth_flow() -> TokenData:
    """
    Run the interactive OAuth flow with browser authentication.

    Opens the browser for Google sign-in and captures the callback.
    """
    print("\n🔐 Antigravity Authentication")
    print("=" * 40)

    # Generate PKCE pair
    pkce = generate_pkce()

    # Build authorization URL
    auth_url = build_authorization_url(pkce)

    print("\nOpening browser for Google authentication...")
    print(f"\nIf browser doesn't open, visit:\n{auth_url}\n")

    # Open browser
    webbrowser.open(auth_url)

    # Start callback server in a thread
    print("Waiting for authentication callback...")

    loop = asyncio.get_event_loop()
    code, state, error = await loop.run_in_executor(None, run_oauth_server)

    if error:
        raise Exception(f"OAuth error: {error}")

    if not code:
        raise Exception("No authorization code received")

    # Decode state to get verifier
    if state:
        verifier, project_id = decode_state(state)
    else:
        verifier = pkce.verifier
        project_id = ""

    print("Exchanging authorization code for tokens...")

    # Exchange code for tokens
    access_token, refresh_token, expires_in, email = await exchange_code_for_tokens(
        code, verifier
    )

    # Calculate expiry timestamp
    expires_at = datetime.now(timezone.utc).timestamp() + expires_in

    # Fetch project ID if not already set
    if not project_id:
        print("Fetching project ID...")
        project_id = await fetch_project_id(access_token)

    if not project_id:
        project_id = ANTIGRAVITY_DEFAULT_PROJECT_ID
        print(f"Using default project ID: {project_id}")

    tokens = TokenData(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        email=email,
        project_id=project_id,
    )

    # Save tokens
    save_tokens(tokens)

    print(f"\n✅ Authentication successful!")
    if email:
        print(f"   Logged in as: {email}")
    print(f"   Project ID: {project_id}")
    print(f"   Tokens saved to: {get_token_storage_path()}")

    return tokens


async def ensure_valid_tokens(force_refresh: bool = False) -> TokenData:
    """
    Ensure we have valid tokens, refreshing or re-authenticating as needed.
    """
    tokens = load_stored_tokens()

    # No stored tokens - need to authenticate
    if tokens is None:
        return await interactive_oauth_flow()

    # Check if token needs refresh
    if force_refresh or is_token_expired(tokens):
        try:
            access_token, expires_in = await refresh_access_token(tokens.refresh_token)
            tokens.access_token = access_token
            tokens.expires_at = datetime.now(timezone.utc).timestamp() + expires_in
            save_tokens(tokens)
        except Exception as e:
            if "invalid_grant" in str(e) or "revoked" in str(e).lower():
                # Refresh token is invalid, need to re-authenticate
                print(f"⚠️  Refresh token expired: {e}")
                return await interactive_oauth_flow()
            raise

    return tokens


def clear_stored_tokens() -> None:
    """Clear stored tokens from disk."""
    path = get_token_storage_path()
    if path.exists():
        path.unlink()
        print(f"Cleared tokens from {path}")
