"""OAuth authentication and token management for OpenAI Codex."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import secrets
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from .constants import (
    CODEX_AUTHORIZE_EXTRA_PARAMS,
    CODEX_AUTHORIZE_URL,
    CODEX_CALLBACK_PATH,
    CODEX_CALLBACK_PORT,
    CODEX_CLIENT_ID,
    CODEX_REDIRECT_URI,
    CODEX_SCOPES,
    CODEX_TOKEN_URL,
    TOKEN_STORAGE_PATH,
)


@dataclass
class TokenData:
    """Stored OAuth token data."""

    access_token: str
    refresh_token: str
    expires_at: float
    id_token: str | None = None
    email: str | None = None
    account_id: str | None = None
    plan_type: str | None = None


@dataclass
class PKCEPair:
    """PKCE code verifier/challenge pair."""

    verifier: str
    challenge: str


def generate_pkce() -> PKCEPair:
    """Generate a PKCE verifier/challenge pair."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return PKCEPair(verifier=verifier, challenge=challenge)


def get_token_storage_path() -> Path:
    """Return the token storage file path."""
    return Path(os.path.expanduser(TOKEN_STORAGE_PATH))


def load_stored_tokens() -> TokenData | None:
    """Load stored token data from disk."""
    path = get_token_storage_path()
    if not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    try:
        return TokenData(
            access_token=data.get("access_token", ""),
            refresh_token=data["refresh_token"],
            expires_at=float(data.get("expires_at", 0)),
            id_token=data.get("id_token"),
            email=data.get("email"),
            account_id=data.get("account_id"),
            plan_type=data.get("plan_type"),
        )
    except (KeyError, TypeError, ValueError):
        return None


def save_tokens(tokens: TokenData) -> None:
    """Persist token data to disk."""
    path = get_token_storage_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "expires_at": tokens.expires_at,
        "id_token": tokens.id_token,
        "email": tokens.email,
        "account_id": tokens.account_id,
        "plan_type": tokens.plan_type,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    os.chmod(path, 0o600)


def clear_stored_tokens() -> None:
    """Delete stored tokens from disk."""
    path = get_token_storage_path()
    if path.exists():
        path.unlink()


def is_token_expired(tokens: TokenData, buffer_seconds: int = 300) -> bool:
    """Return True when token is expired or close to expiry."""
    now = datetime.now(timezone.utc).timestamp()
    return now >= (tokens.expires_at - buffer_seconds)


def _decode_jwt_payload(token: str) -> dict[str, Any] | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None

    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(f"{payload}{padding}").decode("utf-8")
        value = json.loads(decoded)
    except (ValueError, json.JSONDecodeError):
        return None

    return value if isinstance(value, dict) else None


def extract_identity_claims(
    id_token: str | None,
    access_token: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    """Extract email, account id, and plan from available JWTs."""
    email: str | None = None
    account_id: str | None = None
    plan_type: str | None = None

    for token in (id_token, access_token):
        if not token:
            continue

        claims = _decode_jwt_payload(token)
        if not claims:
            continue

        if email is None:
            email = claims.get("email")

        profile_claims = claims.get("https://api.openai.com/profile")
        if email is None and isinstance(profile_claims, dict):
            profile_email = profile_claims.get("email")
            if isinstance(profile_email, str):
                email = profile_email

        auth_claims = claims.get("https://api.openai.com/auth")
        if isinstance(auth_claims, dict):
            if account_id is None:
                account = auth_claims.get("chatgpt_account_id")
                if isinstance(account, str):
                    account_id = account

            if plan_type is None:
                plan = auth_claims.get("chatgpt_plan_type")
                if isinstance(plan, str):
                    plan_type = plan

    return email, account_id, plan_type


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP callback handler for local OAuth capture."""

    code: str | None = None
    state: str | None = None
    error: str | None = None

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        pass

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != CODEX_CALLBACK_PATH:
            self.send_error(404)
            return

        query = parse_qs(parsed.query)

        if "error" in query:
            OAuthCallbackHandler.error = query.get("error", [None])[0]
            self._send_response("Authentication failed. You can close this window.")
            return

        OAuthCallbackHandler.code = query.get("code", [None])[0]
        OAuthCallbackHandler.state = query.get("state", [None])[0]

        if OAuthCallbackHandler.code:
            self._send_response("Authentication complete. You can close this window.")
        else:
            OAuthCallbackHandler.error = "No authorization code received"
            self._send_response("Authentication failed. No code received.")

    def _send_response(self, message: str) -> None:
        html = f"""<!DOCTYPE html>
<html>
<head><title>Codex Authentication</title></head>
<body>
    <h1>Codex Auth</h1>
    <p>{message}</p>
</body>
</html>"""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))


def run_oauth_server(timeout: int = 180) -> tuple[str | None, str | None, str | None]:
    """Run local callback server and return (code, state, error)."""
    OAuthCallbackHandler.code = None
    OAuthCallbackHandler.state = None
    OAuthCallbackHandler.error = None

    server = HTTPServer(("localhost", CODEX_CALLBACK_PORT), OAuthCallbackHandler)
    server.timeout = timeout
    server.handle_request()
    server.server_close()

    return (
        OAuthCallbackHandler.code,
        OAuthCallbackHandler.state,
        OAuthCallbackHandler.error,
    )


def build_authorization_url(pkce: PKCEPair, state: str) -> str:
    """Build the OpenAI OAuth authorization URL."""
    params: dict[str, str] = {
        "response_type": "code",
        "client_id": CODEX_CLIENT_ID,
        "redirect_uri": CODEX_REDIRECT_URI,
        "scope": " ".join(CODEX_SCOPES),
        "code_challenge": pkce.challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    params.update(CODEX_AUTHORIZE_EXTRA_PARAMS)
    return f"{CODEX_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(
    code: str,
    verifier: str,
) -> tuple[str, str, str | None, int, str | None, str | None, str | None]:
    """Exchange authorization code for OAuth tokens."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            CODEX_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": CODEX_CLIENT_ID,
                "code": code,
                "code_verifier": verifier,
                "redirect_uri": CODEX_REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if response.status_code != 200:
        raise Exception(f"Token exchange failed: {response.text}")

    data = response.json()
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    id_token = data.get("id_token")
    expires_in = int(data.get("expires_in", 3600))

    if not isinstance(access_token, str) or not isinstance(refresh_token, str):
        raise Exception(f"Token exchange response missing fields: {data}")

    email, account_id, plan_type = extract_identity_claims(id_token, access_token)
    return (
        access_token,
        refresh_token,
        id_token if isinstance(id_token, str) else None,
        expires_in,
        email,
        account_id,
        plan_type,
    )


async def refresh_access_token(
    refresh_token: str,
) -> tuple[str, str, str | None, int, str | None, str | None, str | None]:
    """Refresh access token using refresh token."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            CODEX_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": CODEX_CLIENT_ID,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if response.status_code != 200:
        detail = response.text
        try:
            payload = response.json()
            if payload.get("error"):
                detail = f"{payload.get('error')}: {payload.get('error_description', '')}".strip()
        except Exception:
            pass
        raise Exception(f"Token refresh failed: {detail}")

    data = response.json()
    access_token = data.get("access_token")
    rotated_refresh_token = data.get("refresh_token", refresh_token)
    id_token = data.get("id_token")
    expires_in = int(data.get("expires_in", 3600))

    if not isinstance(access_token, str):
        raise Exception(f"Token refresh response missing access token: {data}")
    if not isinstance(rotated_refresh_token, str):
        rotated_refresh_token = refresh_token

    email, account_id, plan_type = extract_identity_claims(id_token, access_token)
    return (
        access_token,
        rotated_refresh_token,
        id_token if isinstance(id_token, str) else None,
        expires_in,
        email,
        account_id,
        plan_type,
    )


async def interactive_oauth_flow() -> TokenData:
    """Run interactive OAuth in browser and persist resulting tokens."""
    print("\nCodex OAuth Authentication")
    print("=" * 40)

    pkce = generate_pkce()
    state = secrets.token_urlsafe(24)
    auth_url = build_authorization_url(pkce, state)

    print("Opening browser for OpenAI authentication...")
    print(f"If browser does not open, visit:\n{auth_url}\n")
    webbrowser.open(auth_url)

    print("Waiting for OAuth callback...")
    loop = asyncio.get_running_loop()
    code, callback_state, error = await loop.run_in_executor(None, run_oauth_server)

    if error:
        raise Exception(f"OAuth error: {error}")
    if not code:
        raise Exception("No authorization code received")
    if callback_state != state:
        raise Exception("State mismatch in OAuth callback")

    print("Exchanging authorization code for tokens...")
    (
        access_token,
        refresh_token,
        id_token,
        expires_in,
        email,
        account_id,
        plan_type,
    ) = await exchange_code_for_tokens(code, pkce.verifier)

    if not account_id:
        raise Exception(
            "Missing ChatGPT account ID in token claims. Make sure your account has Codex access."
        )

    tokens = TokenData(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=datetime.now(timezone.utc).timestamp() + expires_in,
        id_token=id_token,
        email=email,
        account_id=account_id,
        plan_type=plan_type,
    )
    save_tokens(tokens)

    print("Authentication successful.")
    if email:
        print(f"  Logged in as: {email}")
    print(f"  Account ID: {account_id}")
    print(f"  Tokens saved to: {get_token_storage_path()}")
    return tokens


async def ensure_valid_tokens(force_refresh: bool = False) -> TokenData:
    """Ensure token set exists and is valid, refreshing when needed."""
    tokens = load_stored_tokens()
    if tokens is None:
        return await interactive_oauth_flow()

    if force_refresh or is_token_expired(tokens):
        try:
            (
                access_token,
                refresh_token,
                id_token,
                expires_in,
                email,
                account_id,
                plan_type,
            ) = await refresh_access_token(tokens.refresh_token)
        except Exception as exc:
            message = str(exc).lower()
            if "invalid_grant" in message or "expired" in message or "revoked" in message:
                print("Stored refresh token is invalid. Re-authentication required.")
                return await interactive_oauth_flow()
            raise

        tokens.access_token = access_token
        tokens.refresh_token = refresh_token
        tokens.expires_at = datetime.now(timezone.utc).timestamp() + expires_in
        if id_token:
            tokens.id_token = id_token
        if email:
            tokens.email = email
        if account_id:
            tokens.account_id = account_id
        if plan_type:
            tokens.plan_type = plan_type
        save_tokens(tokens)

    if not tokens.account_id:
        _, account_id, plan_type = extract_identity_claims(tokens.id_token, tokens.access_token)
        if account_id:
            tokens.account_id = account_id
        if plan_type:
            tokens.plan_type = plan_type
        if account_id or plan_type:
            save_tokens(tokens)

    return tokens
