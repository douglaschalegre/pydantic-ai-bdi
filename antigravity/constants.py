"""
Constants for Antigravity OAuth flows and Cloud Code Assist API integration.

Based on: https://github.com/NoeFabris/opencode-antigravity-auth
"""

from typing import Literal

# OAuth Client Credentials (from Antigravity/Google IDE)
ANTIGRAVITY_CLIENT_ID = "1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com"
ANTIGRAVITY_CLIENT_SECRET = "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"

# OAuth Scopes required for Antigravity
ANTIGRAVITY_SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/cclog",
    "https://www.googleapis.com/auth/experimentsandconfigs",
]

# OAuth Redirect URI - local callback server
ANTIGRAVITY_REDIRECT_URI = "http://localhost:51121/oauth-callback"
OAUTH_CALLBACK_PORT = 51121

# API Endpoints (in fallback order: daily → autopush → prod)
ANTIGRAVITY_ENDPOINT_DAILY = "https://daily-cloudcode-pa.sandbox.googleapis.com"
ANTIGRAVITY_ENDPOINT_AUTOPUSH = "https://autopush-cloudcode-pa.sandbox.googleapis.com"
ANTIGRAVITY_ENDPOINT_PROD = "https://cloudcode-pa.googleapis.com"

ANTIGRAVITY_ENDPOINT_FALLBACKS = [
    ANTIGRAVITY_ENDPOINT_DAILY,
    ANTIGRAVITY_ENDPOINT_AUTOPUSH,
    ANTIGRAVITY_ENDPOINT_PROD,
]

# Primary endpoint (daily sandbox - same as CLIProxy/Vibeproxy)
ANTIGRAVITY_ENDPOINT = ANTIGRAVITY_ENDPOINT_DAILY

# Gemini CLI endpoint (production) - for models without :antigravity suffix
GEMINI_CLI_ENDPOINT = ANTIGRAVITY_ENDPOINT_PROD

# Default project ID fallback (used when Antigravity doesn't return one)
ANTIGRAVITY_DEFAULT_PROJECT_ID = "rising-fact-p41fc"

# Request headers
ANTIGRAVITY_HEADERS = {
    "User-Agent": "antigravity/1.11.5 windows/amd64",
    "X-Goog-Api-Client": "google-cloud-sdk vscode_cloudshelleditor/0.1",
    "Client-Metadata": '{"ideType":"IDE_UNSPECIFIED","platform":"PLATFORM_UNSPECIFIED","pluginType":"GEMINI"}',
}

GEMINI_CLI_HEADERS = {
    "User-Agent": "google-api-nodejs-client/9.15.1",
    "X-Goog-Api-Client": "gl-node/22.17.0",
    "Client-Metadata": "ideType=IDE_UNSPECIFIED,platform=PLATFORM_UNSPECIFIED,pluginType=GEMINI",
}

# Header style type
HeaderStyle = Literal["antigravity", "gemini-cli"]

# Token storage path
TOKEN_STORAGE_PATH = "~/.antigravity_tokens.json"

# Available Models
ANTIGRAVITY_MODELS = {
    # Claude models (Antigravity quota)
    "claude-sonnet-4-5": {
        "name": "Claude Sonnet 4.5",
        "family": "claude",
        "thinking": False,
        "context_limit": 200000,
        "output_limit": 64000,
    },
    "claude-sonnet-4-5-thinking": {
        "name": "Claude Sonnet 4.5 Thinking",
        "family": "claude",
        "thinking": True,
        "context_limit": 200000,
        "output_limit": 64000,
        "default_thinking_budget": 8192,
    },
    "claude-opus-4-5-thinking": {
        "name": "Claude Opus 4.5 Thinking",
        "family": "claude",
        "thinking": True,
        "context_limit": 200000,
        "output_limit": 64000,
        "default_thinking_budget": 8192,
    },
    # Gemini 3 models (Antigravity quota)
    "gemini-3-pro": {
        "name": "Gemini 3 Pro",
        "family": "gemini",
        "thinking": True,
        "context_limit": 1048576,
        "output_limit": 65535,
        "default_thinking_level": "high",
    },
    "gemini-3-pro-high": {
        "name": "Gemini 3 Pro (High Thinking)",
        "family": "gemini",
        "thinking": True,
        "context_limit": 1048576,
        "output_limit": 65535,
        "thinking_level": "high",
    },
    "gemini-3-pro-low": {
        "name": "Gemini 3 Pro (Low Thinking)",
        "family": "gemini",
        "thinking": True,
        "context_limit": 1048576,
        "output_limit": 65535,
        "thinking_level": "low",
    },
    "gemini-3-flash": {
        "name": "Gemini 3 Flash",
        "family": "gemini",
        "thinking": True,
        "context_limit": 1048576,
        "output_limit": 65536,
        "default_thinking_level": "medium",
    },
    # Gemini 2.5 models (Gemini CLI quota)
    "gemini-2.5-flash": {
        "name": "Gemini 2.5 Flash",
        "family": "gemini",
        "thinking": False,
        "context_limit": 1048576,
        "output_limit": 65536,
        "quota": "gemini-cli",
    },
    "gemini-2.5-pro": {
        "name": "Gemini 2.5 Pro",
        "family": "gemini",
        "thinking": False,
        "context_limit": 1048576,
        "output_limit": 65536,
        "quota": "gemini-cli",
    },
}

# Model family type
ModelFamily = Literal["claude", "gemini"]
