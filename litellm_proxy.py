"""OpenAI-compatible model factory for the local LiteLLM proxy."""

from __future__ import annotations

import os

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider


DEFAULT_LITELLM_BASE_URL = "http://localhost:4000"


def create_litellm_model(
    model_name: str,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
) -> OpenAIChatModel:
    """Create a Pydantic AI chat model backed by a local LiteLLM proxy."""

    resolved_base_url = base_url or os.getenv(
        "LITELLM_BASE_URL", DEFAULT_LITELLM_BASE_URL
    )
    resolved_api_key = api_key or os.getenv("LITELLM_API_KEY") or os.getenv(
        "OPENAI_API_KEY"
    )
    if not resolved_api_key:
        raise RuntimeError(
            "LiteLLM authentication is not configured; set LITELLM_API_KEY "
            "or pass api_key explicitly."
        )

    provider = OpenAIProvider(
        base_url=resolved_base_url,
        api_key=resolved_api_key,
    )
    return OpenAIChatModel(model_name, provider=provider)


__all__ = [
    "DEFAULT_LITELLM_BASE_URL",
    "create_litellm_model",
]
