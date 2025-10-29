"""General model factory supporting multiple Pydantic AI providers.

Selection is driven by environment variables:
  LLM_PROVIDER: one of openai, ollama, anthropic, groq, mistral, cohere, bedrock, huggingface
  LLM_MODEL_NAME: the underlying model id (provider-specific). If omitted, a provider default is chosen.
  PROVIDER_API_KEY: generic key if provider-specific key not set; otherwise provider-specific keys:
      OPENAI_API_KEY, ANTHROPIC_API_KEY, GROQ_API_KEY, MISTRAL_API_KEY, COHERE_API_KEY, HUGGINGFACE_API_KEY
  OLLAMA_BASE_URL: base URL for ollama (default http://localhost:11434/v1)

Minimal defaults are intentionally conservative; adjust to your environment.
"""

from __future__ import annotations
import os
from pydantic_ai.models.openai import OpenAIChatModel

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "ollama": "gemma3:1b",
    "anthropic": "claude-3-5-sonnet-latest",
    "groq": "llama-3.1-8b-instant",
    "mistral": "mistral-large-latest",
    "cohere": "command-r-plus",
    "bedrock": "amazon.titan-text-lite-v1",
    "huggingface": "distilbert-base-uncased",
}


def _env(key: str, default: str | None = None) -> str | None:
    return os.getenv(key) or (default if default is not None else None)


def _select_model_name(provider: str) -> str:
    return _env("LLM_MODEL_NAME") or DEFAULT_MODELS.get(provider, "gpt-4o-mini")


def _build_openai(model_name: str):
    from pydantic_ai.providers.openai import OpenAIProvider

    api_key = _env("OPENAI_API_KEY") or _env("PROVIDER_API_KEY")
    if not api_key:
        return OpenAIChatModel(model_name)  # fallback; prompts will fail gracefully
    return OpenAIChatModel(model_name, provider=OpenAIProvider(api_key=api_key))


def _build_ollama(model_name: str):
    from pydantic_ai.providers.ollama import OllamaProvider

    base_url = _env("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    api_key = _env("OLLAMA_API_KEY")
    return OpenAIChatModel(
        model_name, provider=OllamaProvider(base_url=base_url, api_key=api_key)
    )


def _build_anthropic(model_name: str):
    from pydantic_ai.models.anthropic import AnthropicModel

    api_key = _env("ANTHROPIC_API_KEY") or _env("PROVIDER_API_KEY")
    if not api_key:
        return AnthropicModel(model_name)  # will error on call without key but created
    from pydantic_ai.providers.anthropic import AnthropicProvider

    return AnthropicModel(model_name, provider=AnthropicProvider(api_key=api_key))


def _build_groq(model_name: str):
    from pydantic_ai.models.groq import GroqModel

    api_key = _env("GROQ_API_KEY") or _env("PROVIDER_API_KEY")
    if not api_key:
        return GroqModel(model_name)
    from pydantic_ai.providers.groq import GroqProvider

    return GroqModel(model_name, provider=GroqProvider(api_key=api_key))


def _build_mistral(model_name: str):
    from pydantic_ai.models.mistral import MistralModel

    api_key = _env("MISTRAL_API_KEY") or _env("PROVIDER_API_KEY")
    if not api_key:
        return MistralModel(model_name)
    from pydantic_ai.providers.mistral import MistralProvider

    return MistralModel(model_name, provider=MistralProvider(api_key=api_key))


def _build_cohere(model_name: str):
    from pydantic_ai.models.cohere import CohereModel

    api_key = _env("COHERE_API_KEY") or _env("PROVIDER_API_KEY")
    if not api_key:
        return CohereModel(model_name)
    from pydantic_ai.providers.cohere import CohereProvider

    return CohereModel(model_name, provider=CohereProvider(api_key=api_key))


def _build_bedrock(model_name: str):
    from pydantic_ai.models.bedrock import BedrockModel

    # Bedrock auth typically uses AWS creds; rely on environment / default chain
    return BedrockModel(model_name)


def _build_huggingface(model_name: str):
    from pydantic_ai.models.huggingface import HuggingFaceModel

    api_key = _env("HUGGINGFACE_API_KEY") or _env("PROVIDER_API_KEY")
    if not api_key:
        return HuggingFaceModel(model_name)
    from pydantic_ai.providers.huggingface import HuggingFaceProvider

    return HuggingFaceModel(model_name, provider=HuggingFaceProvider(api_key=api_key))


BUILDERS = {
    "openai": _build_openai,
    "ollama": _build_ollama,
    "anthropic": _build_anthropic,
    "groq": _build_groq,
    "mistral": _build_mistral,
    "cohere": _build_cohere,
    "bedrock": _build_bedrock,
    "huggingface": _build_huggingface,
}


def build_model(provider: str | None = None):
    """Instantiate a model for the requested provider.

    Raises KeyError if provider is unknown. Caller can catch and fallback.
    """
    prov = (provider or _env("LLM_PROVIDER") or "ollama").lower()
    model_name = _select_model_name(prov)
    builder = BUILDERS.get(prov)
    if not builder:
        raise KeyError(
            f"Unsupported provider '{prov}'. Supported: {sorted(BUILDERS.keys())}"
        )
    return builder(model_name)
