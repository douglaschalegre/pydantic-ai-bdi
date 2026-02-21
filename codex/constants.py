"""Constants for OpenAI Codex OAuth and model defaults."""

from typing import Literal

# OAuth configuration
CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
CODEX_AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
CODEX_TOKEN_URL = "https://auth.openai.com/oauth/token"
CODEX_REDIRECT_URI = "http://localhost:1455/auth/callback"
CODEX_CALLBACK_PATH = "/auth/callback"
CODEX_CALLBACK_PORT = 1455
CODEX_SCOPES = ["openid", "profile", "email", "offline_access"]

CODEX_AUTHORIZE_EXTRA_PARAMS = {
    "id_token_add_organizations": "true",
    "codex_cli_simplified_flow": "true",
    "originator": "codex_cli_rs",
}

# API configuration
CODEX_API_BASE_URL = "https://chatgpt.com/backend-api/codex"
CODEX_OPENAI_BETA = "responses=experimental"
CODEX_ORIGINATOR = "codex_cli_rs"
CODEX_DEFAULT_INSTRUCTIONS = (
    "You are an AI assistant. Follow the provided user instructions."
)

# Token storage
TOKEN_STORAGE_PATH = "~/.codex_oauth_tokens.json"

# Model defaults
CODEX_DEFAULT_MODEL = "gpt-5.3-codex"

CODEX_MODEL_ALIASES = {
    "openai-codex/gpt-5.3-codex": "gpt-5.3-codex",
    "openai-codex/gpt-5.2-codex": "gpt-5.2-codex",
    "openai-codex/gpt-5.1-codex": "gpt-5.1-codex",
    "openai-codex/gpt-5-codex": "gpt-5-codex",
    "openai-codex/codex-mini-latest": "codex-mini-latest",
}

CodexModelName = Literal[
    "gpt-5.3-codex",
    "gpt-5.2-codex",
    "gpt-5.1-codex",
    "gpt-5-codex",
    "codex-mini-latest",
]
