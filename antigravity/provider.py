"""
Antigravity Provider for pydantic-ai.

Handles authentication and provides an HTTP client for the Antigravity API.
"""

import httpx

from .auth import TokenData, ensure_valid_tokens, is_token_expired, refresh_access_token, save_tokens
from .constants import (
    ANTIGRAVITY_ENDPOINT,
    ANTIGRAVITY_HEADERS,
    GEMINI_CLI_ENDPOINT,
    GEMINI_CLI_HEADERS,
    ANTIGRAVITY_MODELS,
    HeaderStyle,
)


class AntigravityProvider:
    """
    Provider for Antigravity API authentication and HTTP client management.

    Handles:
    - OAuth token management (load, refresh, re-authenticate)
    - HTTP client with proper headers
    - Endpoint selection based on model
    """

    def __init__(
        self,
        tokens: TokenData | None = None,
        header_style: HeaderStyle = "antigravity",
    ):
        """
        Initialize the Antigravity provider.

        Args:
            tokens: Pre-loaded tokens (will trigger OAuth flow if None)
            header_style: Which header style to use ("antigravity" or "gemini-cli")
        """
        self._tokens = tokens
        self._header_style = header_style
        self._client: httpx.AsyncClient | None = None
        self._initialized = False

    @property
    def name(self) -> str:
        """Provider name."""
        return "antigravity"

    @property
    def base_url(self) -> str:
        """Base URL for API requests."""
        if self._header_style == "gemini-cli":
            return GEMINI_CLI_ENDPOINT
        return ANTIGRAVITY_ENDPOINT

    async def initialize(self) -> None:
        """Initialize the provider, ensuring valid tokens."""
        if self._initialized:
            return

        if self._tokens is None:
            self._tokens = await ensure_valid_tokens()

        self._initialized = True

    async def get_tokens(self) -> TokenData:
        """Get valid tokens, refreshing if necessary."""
        await self.initialize()

        if self._tokens is None:
            self._tokens = await ensure_valid_tokens()

        # Check if we need to refresh
        if is_token_expired(self._tokens):
            from datetime import datetime, timezone

            access_token, expires_in = await refresh_access_token(
                self._tokens.refresh_token
            )
            self._tokens.access_token = access_token
            self._tokens.expires_at = datetime.now(timezone.utc).timestamp() + expires_in
            save_tokens(self._tokens)

        return self._tokens

    @property
    def project_id(self) -> str | None:
        """Get the current project ID."""
        return self._tokens.project_id if self._tokens else None

    def get_headers(self) -> dict[str, str]:
        """Get request headers based on header style."""
        if self._header_style == "gemini-cli":
            return dict(GEMINI_CLI_HEADERS)
        return dict(ANTIGRAVITY_HEADERS)

    async def get_client(self) -> httpx.AsyncClient:
        """Get an authenticated HTTP client."""
        tokens = await self.get_tokens()

        headers = self.get_headers()
        headers["Authorization"] = f"Bearer {tokens.access_token}"
        headers["Content-Type"] = "application/json"

        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=httpx.Timeout(120.0, connect=30.0),
            )

        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def get_endpoint_for_model(self, model_name: str) -> str:
        """Get the appropriate endpoint for a model."""
        model_info = ANTIGRAVITY_MODELS.get(model_name, {})
        if model_info.get("quota") == "gemini-cli":
            return GEMINI_CLI_ENDPOINT
        return ANTIGRAVITY_ENDPOINT

    def get_header_style_for_model(self, model_name: str) -> HeaderStyle:
        """Get the appropriate header style for a model."""
        model_info = ANTIGRAVITY_MODELS.get(model_name, {})
        if model_info.get("quota") == "gemini-cli":
            return "gemini-cli"
        return "antigravity"

    async def __aenter__(self) -> "AntigravityProvider":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()


async def create_provider(
    header_style: HeaderStyle = "antigravity",
) -> AntigravityProvider:
    """
    Factory function to create an initialized Antigravity provider.

    Usage:
        provider = await create_provider()
        # or
        async with create_provider() as provider:
            ...
    """
    provider = AntigravityProvider(header_style=header_style)
    await provider.initialize()
    return provider
