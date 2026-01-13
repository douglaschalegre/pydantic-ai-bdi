"""
Antigravity - Google's Unified Gateway API provider for pydantic-ai.

This module provides access to Claude, Gemini, and other models through
Google's Antigravity API using OAuth authentication.

Example usage:
    ```python
    from antigravity import AntigravityModel, AntigravityProvider

    # Create provider (will trigger OAuth flow on first use)
    provider = AntigravityProvider()

    # Create model
    model = AntigravityModel(
        "claude-sonnet-4-5-thinking",
        provider=provider,
        thinking_budget=8192,
    )

    # Use with pydantic-ai Agent or directly
    from bdi import BDI

    agent = BDI(
        model,
        desires=["Help the user"],
        intentions=["Be helpful"],
    )
    ```

Available models:
    - claude-sonnet-4-5: Claude Sonnet 4.5
    - claude-sonnet-4-5-thinking: Claude Sonnet 4.5 with extended thinking
    - claude-opus-4-5-thinking: Claude Opus 4.5 with extended thinking
    - gemini-3-pro: Gemini 3 Pro
    - gemini-3-pro-high: Gemini 3 Pro (high thinking)
    - gemini-3-pro-low: Gemini 3 Pro (low thinking)
    - gemini-3-flash: Gemini 3 Flash
    - gemini-2.5-flash: Gemini 2.5 Flash
    - gemini-2.5-pro: Gemini 2.5 Pro
"""

from .auth import (
    TokenData,
    ensure_valid_tokens,
    interactive_oauth_flow,
    load_stored_tokens,
    save_tokens,
    clear_stored_tokens,
    is_token_expired,
    refresh_access_token,
)

from .constants import (
    ANTIGRAVITY_ENDPOINT,
    ANTIGRAVITY_MODELS,
    ANTIGRAVITY_SCOPES,
)

from .model import (
    AntigravityModel,
    AntigravityModelName,
    create_model,
)

from .provider import (
    AntigravityProvider,
    create_provider,
)

__all__ = [
    # Main classes
    "AntigravityModel",
    "AntigravityProvider",
    # Factory functions
    "create_model",
    "create_provider",
    # Auth utilities
    "TokenData",
    "ensure_valid_tokens",
    "interactive_oauth_flow",
    "load_stored_tokens",
    "save_tokens",
    "clear_stored_tokens",
    "is_token_expired",
    "refresh_access_token",
    # Constants
    "ANTIGRAVITY_ENDPOINT",
    "ANTIGRAVITY_MODELS",
    "ANTIGRAVITY_SCOPES",
    "AntigravityModelName",
]

__version__ = "0.1.0"
