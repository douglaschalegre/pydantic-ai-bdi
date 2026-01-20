"""CrewAI LLM adapter for Antigravity models."""

from __future__ import annotations

from typing import Any

import asyncio
from concurrent.futures import ThreadPoolExecutor

from crewai.llms.base_llm import BaseLLM
from crewai.llms.base_llm import DEFAULT_CONTEXT_WINDOW_SIZE
from pydantic_ai.direct import model_request
from pydantic_ai.messages import ModelRequest, TextPart


class AntigravityCrewAILLM(BaseLLM):
    """Minimal CrewAI LLM adapter for Antigravity models."""

    def __init__(
        self,
        model,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> None:
        self._antigravity_model = model
        super().__init__(model=model.model_name, temperature=temperature, **kwargs)

    def call(
        self,
        messages,
        tools=None,
        callbacks=None,
        available_functions=None,
        from_task=None,
        from_agent=None,
        response_model=None,
    ) -> str | Any:
        self._emit_call_started_event(
            messages=messages,
            tools=tools,
            callbacks=callbacks,
            available_functions=available_functions,
            from_task=from_task,
            from_agent=from_agent,
        )

        try:
            prompt = _normalize_messages(messages)
            request = ModelRequest.user_text_prompt(prompt)
            response = _run_sync(model_request(self._antigravity_model, [request]))
            content = _extract_text(response.parts)
            content = self._apply_stop_words(content)
            self._emit_call_completed_event(
                response=content,
                call_type="llm_call",
                from_task=from_task,
                from_agent=from_agent,
                messages=messages if isinstance(messages, list) else None,
            )
            return content
        except Exception as exc:
            self._emit_call_failed_event(
                error=str(exc),
                from_task=from_task,
                from_agent=from_agent,
            )
            raise

    def get_context_window_size(self) -> int:
        return DEFAULT_CONTEXT_WINDOW_SIZE


def _normalize_messages(messages) -> str:
    if isinstance(messages, str):
        return messages
    if not isinstance(messages, list):
        return str(messages)

    parts = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        parts.append(f"{role}: {content}")
    return "\n".join(parts).strip()


def _extract_text(parts) -> str:
    for part in parts:
        if isinstance(part, TextPart) and part.content:
            return part.content
    for part in parts:
        if hasattr(part, "content") and part.content:
            return str(part.content)
    return ""


def _run_sync(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(lambda: asyncio.run(coro)).result()

    return asyncio.run(coro)
