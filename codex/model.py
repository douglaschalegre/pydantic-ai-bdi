"""OpenAI Codex model wrapper for pydantic-ai."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from pydantic_ai import ModelHTTPError
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models import ModelRequestParameters, StreamedResponse
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.settings import ModelSettings

from .constants import CODEX_DEFAULT_MODEL, CODEX_MODEL_ALIASES, CodexModelName
from .provider import CodexProvider


def normalize_model_name(model_name: str) -> str:
    """Normalize friendly or prefixed model names to API model names."""
    name = model_name.strip()
    if not name:
        return CODEX_DEFAULT_MODEL

    if name in CODEX_MODEL_ALIASES:
        return CODEX_MODEL_ALIASES[name]

    prefix = "openai-codex/"
    if name.startswith(prefix):
        return name[len(prefix) :]

    return name


class CodexModel(OpenAIResponsesModel):
    """Pydantic AI model that uses OpenAI Codex OAuth-backed requests."""

    def __init__(
        self,
        model_name: CodexModelName | str = CODEX_DEFAULT_MODEL,
        *,
        provider: CodexProvider | None = None,
        settings: ModelSettings | None = None,
    ):
        self._codex_provider = provider or CodexProvider()
        resolved_model_name = normalize_model_name(model_name)
        super().__init__(resolved_model_name, provider=self._codex_provider, settings=settings)

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        await self._codex_provider.initialize()

        async def _stream_to_response() -> ModelResponse:
            async with super(CodexModel, self).request_stream(
                messages,
                model_settings,
                model_request_parameters,
                run_context=None,
            ) as streamed_response:
                async for _ in streamed_response:
                    pass
                return streamed_response.get()

        try:
            response = await _stream_to_response()
        except ModelHTTPError as exc:
            if exc.status_code != 401:
                raise
            await self._codex_provider.force_refresh()
            response = await _stream_to_response()

        self._record_usage(response.usage.input_tokens, response.usage.output_tokens)

        return response

    @asynccontextmanager
    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
        run_context: Any | None = None,
    ) -> AsyncIterator[StreamedResponse]:
        await self._codex_provider.initialize()
        try:
            async with super().request_stream(
                messages,
                model_settings,
                model_request_parameters,
                run_context=run_context,
            ) as response:
                self._record_usage(None, None)
                yield response
            return
        except ModelHTTPError as exc:
            if exc.status_code != 401:
                raise

        await self._codex_provider.force_refresh()
        async with super().request_stream(
            messages,
            model_settings,
            model_request_parameters,
            run_context=run_context,
        ) as response:
            self._record_usage(None, None)
            yield response

    def _record_usage(self, input_tokens: int | None, output_tokens: int | None) -> None:
        tracker = self._codex_provider.usage_tracker
        if tracker is None:
            return

        record = getattr(tracker, "record", None)
        if callable(record):
            record(input_tokens, output_tokens)


def create_model(
    model_name: CodexModelName | str = CODEX_DEFAULT_MODEL,
    provider: CodexProvider | None = None,
    usage_tracker: Any | None = None,
    settings: ModelSettings | None = None,
) -> CodexModel:
    """Factory to create a Codex model instance."""
    resolved_provider = provider or CodexProvider(usage_tracker=usage_tracker)
    if usage_tracker is not None:
        resolved_provider.usage_tracker = usage_tracker

    return CodexModel(
        model_name=model_name,
        provider=resolved_provider,
        settings=settings,
    )
