"""OpenAI Codex provider for pydantic-ai."""

from __future__ import annotations

import asyncio
import json

import httpx
from openai import AsyncOpenAI
from pydantic_ai import ModelProfile
from pydantic_ai.profiles.openai import openai_model_profile
from pydantic_ai.providers import Provider

from .auth import TokenData, ensure_valid_tokens, is_token_expired
from .constants import (
    CODEX_API_BASE_URL,
    CODEX_DEFAULT_INSTRUCTIONS,
    CODEX_OPENAI_BETA,
    CODEX_ORIGINATOR,
)


class CodexProvider(Provider[AsyncOpenAI]):
    """Provider that authenticates OpenAI requests via Codex OAuth."""

    def __init__(
        self,
        tokens: TokenData | None = None,
        base_url: str = CODEX_API_BASE_URL,
        usage_tracker: object | None = None,
    ):
        self._tokens = tokens
        self._base_url = base_url
        self.usage_tracker = usage_tracker
        self._lock = asyncio.Lock()

        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=30.0),
            event_hooks={"request": [self._inject_request_headers]},
        )
        self._client = AsyncOpenAI(
            base_url=self._base_url,
            api_key=self._get_access_token,
            http_client=self._http_client,
        )

    @property
    def name(self) -> str:
        return "openai-codex"

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def client(self) -> AsyncOpenAI:
        return self._client

    def model_profile(self, model_name: str) -> ModelProfile | None:
        return openai_model_profile(model_name)

    async def initialize(self) -> None:
        await self.get_tokens()

    async def _get_access_token(self) -> str:
        tokens = await self.get_tokens()
        return tokens.access_token

    async def _inject_request_headers(self, request: httpx.Request) -> None:
        tokens = await self.get_tokens()
        if not tokens.account_id:
            raise RuntimeError(
                "Codex OAuth token is missing account id. Clear tokens and authenticate again."
            )

        request.headers["Authorization"] = f"Bearer {tokens.access_token}"
        request.headers["ChatGPT-Account-ID"] = tokens.account_id
        request.headers["OpenAI-Beta"] = CODEX_OPENAI_BETA
        request.headers["originator"] = CODEX_ORIGINATOR
        self._apply_codex_request_defaults(request)

    def _apply_codex_request_defaults(self, request: httpx.Request) -> None:
        if request.method.upper() != "POST":
            return

        path = request.url.path.rstrip("/")
        if not path.endswith("/responses"):
            return

        content_type = request.headers.get("content-type", "")
        if "application/json" not in content_type.lower():
            return

        try:
            payload = json.loads(request.content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return

        if not isinstance(payload, dict):
            return

        changed = False

        instructions = payload.get("instructions")
        if not isinstance(instructions, str) or not instructions.strip():
            payload["instructions"] = CODEX_DEFAULT_INSTRUCTIONS
            changed = True

        if payload.get("stream") is not True:
            payload["stream"] = True
            changed = True

        if payload.get("store") is not False:
            payload["store"] = False
            changed = True

        include = payload.get("include")
        if isinstance(include, list):
            if "reasoning.encrypted_content" not in include:
                include.append("reasoning.encrypted_content")
                changed = True
        elif include is None:
            payload["include"] = ["reasoning.encrypted_content"]
            changed = True

        if not changed:
            return

        updated_body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        request._content = updated_body
        request.stream = httpx.ByteStream(updated_body)
        request.headers["content-length"] = str(len(updated_body))

    async def get_tokens(self, force_refresh: bool = False) -> TokenData:
        async with self._lock:
            if self._tokens is None:
                self._tokens = await ensure_valid_tokens()
            elif force_refresh or is_token_expired(self._tokens):
                self._tokens = await ensure_valid_tokens(force_refresh=True)

            if not self._tokens.account_id:
                self._tokens = await ensure_valid_tokens(force_refresh=True)

            if not self._tokens.account_id:
                raise RuntimeError(
                    "Codex OAuth token is missing account id. Clear tokens and authenticate again."
                )

            return self._tokens

    async def force_refresh(self) -> TokenData:
        return await self.get_tokens(force_refresh=True)

    async def close(self) -> None:
        if not self._http_client.is_closed:
            await self._http_client.aclose()

    async def __aenter__(self) -> "CodexProvider":
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()


async def create_provider(
    usage_tracker: object | None = None,
) -> CodexProvider:
    """Factory to create an initialized Codex provider."""
    provider = CodexProvider(usage_tracker=usage_tracker)
    await provider.initialize()
    return provider
