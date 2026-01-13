"""
Antigravity Model for pydantic-ai.

Implements the pydantic-ai Model interface for the Antigravity Unified Gateway API,
supporting Claude, Gemini, and other models through Google's unified API.
"""

import asyncio
import json
import re
import uuid
from typing import Any, AsyncIterator, Literal

import httpx


# Rate limit configuration
MAX_RETRIES = 5
INITIAL_BACKOFF_SECONDS = 2.0
MAX_BACKOFF_SECONDS = 60.0
BACKOFF_MULTIPLIER = 2.0


def parse_retry_delay(error_message: str) -> float | None:
    """Extract retry delay from error message like 'reset after 3s'."""
    match = re.search(r'reset after\s+(\d+(?:\.\d+)?)(s|m|h)?', error_message, re.IGNORECASE)
    if match:
        value = float(match.group(1))
        unit = (match.group(2) or 's').lower()
        if unit == 'm':
            return value * 60
        elif unit == 'h':
            return value * 3600
        return value
    return None

from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    TextPart,
    ToolCallPart,
)
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import Usage

from .constants import (
    ANTIGRAVITY_ENDPOINT,
    ANTIGRAVITY_ENDPOINT_FALLBACKS,
    ANTIGRAVITY_HEADERS,
    ANTIGRAVITY_MODELS,
    GEMINI_CLI_ENDPOINT,
    GEMINI_CLI_HEADERS,
    ANTIGRAVITY_DEFAULT_PROJECT_ID,
)
from .provider import AntigravityProvider
from .transform import (
    messages_to_antigravity,
    antigravity_to_response,
    parse_sse_event,
)


# Type alias for available model names
AntigravityModelName = Literal[
    "claude-sonnet-4-5",
    "claude-sonnet-4-5-thinking",
    "claude-opus-4-5-thinking",
    "gemini-3-pro",
    "gemini-3-pro-high",
    "gemini-3-pro-low",
    "gemini-3-flash",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
]


class AntigravityModel(Model):
    """
    pydantic-ai compatible Model for Antigravity API.

    Supports Claude and Gemini models through Google's Antigravity Unified Gateway.

    Example:
        ```python
        from antigravity import AntigravityModel, AntigravityProvider

        provider = AntigravityProvider()
        model = AntigravityModel("claude-sonnet-4-5-thinking", provider=provider)

        agent = Agent(model=model)
        ```
    """

    def __init__(
        self,
        model_name: str,
        *,
        provider: AntigravityProvider | None = None,
        thinking_budget: int | None = None,
        thinking_level: str | None = None,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        settings: ModelSettings | None = None,
    ):
        """
        Initialize the Antigravity model.

        Args:
            model_name: Name of the model to use (e.g., "claude-sonnet-4-5-thinking")
            provider: Optional pre-configured provider
            thinking_budget: Token budget for thinking (Claude models)
            thinking_level: Thinking level for Gemini models ("low", "medium", "high")
            max_output_tokens: Maximum output tokens
            temperature: Sampling temperature
            top_p: Top-p sampling parameter
            top_k: Top-k sampling parameter
            settings: Optional model settings
        """
        super().__init__(settings=settings)

        self._model_name = model_name
        self._provider = provider or AntigravityProvider()

        # Thinking configuration
        self._thinking_budget = thinking_budget
        self._thinking_level = thinking_level

        # Generation settings
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature
        self._top_p = top_p
        self._top_k = top_k

        # Set defaults based on model info
        model_info = ANTIGRAVITY_MODELS.get(model_name, {})

        if model_info.get("thinking") and self._thinking_budget is None:
            if "default_thinking_budget" in model_info:
                self._thinking_budget = model_info["default_thinking_budget"]

        if model_info.get("thinking") and self._thinking_level is None:
            if "thinking_level" in model_info:
                self._thinking_level = model_info["thinking_level"]
            elif "default_thinking_level" in model_info:
                self._thinking_level = model_info["default_thinking_level"]

        if self._max_output_tokens is None:
            self._max_output_tokens = model_info.get("output_limit", 8192)

    @property
    def model_name(self) -> str:
        """The model name."""
        return self._model_name

    @property
    def system(self) -> str:
        """The model provider identifier."""
        return "antigravity"

    def _get_model_family(self) -> str:
        """Get the model family (claude or gemini)."""
        model_info = ANTIGRAVITY_MODELS.get(self._model_name, {})
        return model_info.get("family", "claude" if "claude" in self._model_name else "gemini")

    def _build_generation_config(self) -> dict[str, Any]:
        """Build the generationConfig for the request."""
        config: dict[str, Any] = {}

        if self._max_output_tokens:
            config["maxOutputTokens"] = self._max_output_tokens

        if self._temperature is not None:
            config["temperature"] = self._temperature

        if self._top_p is not None:
            config["topP"] = self._top_p

        if self._top_k is not None:
            config["topK"] = self._top_k

        # Add thinking config
        model_info = ANTIGRAVITY_MODELS.get(self._model_name, {})
        if model_info.get("thinking"):
            family = self._get_model_family()

            if family == "claude" and self._thinking_budget:
                config["thinkingConfig"] = {
                    "thinkingBudget": self._thinking_budget,
                    "includeThoughts": True,
                }
                # Ensure maxOutputTokens > thinkingBudget
                if config.get("maxOutputTokens", 0) <= self._thinking_budget:
                    config["maxOutputTokens"] = self._thinking_budget + 10000

            elif family == "gemini" and self._thinking_level:
                config["thinkingConfig"] = {
                    "thinkingLevel": self._thinking_level,
                    "includeThoughts": True,
                }

        return config

    async def _make_request(
        self,
        contents: list[dict[str, Any]],
        system_instruction: dict[str, Any] | None,
        tools: list[dict[str, Any]] | None,
        stream: bool = False,
        force_tool_calling: bool = False,
    ) -> httpx.Response:
        """Make a request to the Antigravity API with retry logic for rate limits."""
        await self._provider.initialize()

        tokens = await self._provider.get_tokens()
        project_id = tokens.project_id or ANTIGRAVITY_DEFAULT_PROJECT_ID

        # Build request body
        request_body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": self._build_generation_config(),
        }

        if system_instruction:
            request_body["systemInstruction"] = system_instruction

        if tools:
            request_body["tools"] = tools
            # If force_tool_calling is set, configure the model to require tool usage
            if force_tool_calling:
                request_body["toolConfig"] = {
                    "functionCallingConfig": {
                        "mode": "ANY"  # Forces the model to call at least one function
                    }
                }

        # Build outer envelope
        envelope: dict[str, Any] = {
            "project": project_id,
            "model": self._model_name,
            "request": request_body,
            "userAgent": "antigravity",
            "requestId": f"agent-{uuid.uuid4().hex[:12]}",
        }

        # Determine endpoint and headers
        endpoint = self._provider.get_endpoint_for_model(self._model_name)
        header_style = self._provider.get_header_style_for_model(self._model_name)

        if header_style == "gemini-cli":
            headers = dict(GEMINI_CLI_HEADERS)
        else:
            headers = dict(ANTIGRAVITY_HEADERS)

        headers["Authorization"] = f"Bearer {tokens.access_token}"
        headers["Content-Type"] = "application/json"

        if stream:
            headers["Accept"] = "text/event-stream"

        # Retry loop with exponential backoff for rate limits
        last_error: Exception | None = None
        backoff = INITIAL_BACKOFF_SECONDS

        for attempt in range(MAX_RETRIES):
            # Try each endpoint
            for fallback_endpoint in ANTIGRAVITY_ENDPOINT_FALLBACKS:
                if stream:
                    current_url = f"{fallback_endpoint}/v1internal:streamGenerateContent?alt=sse"
                else:
                    current_url = f"{fallback_endpoint}/v1internal:generateContent"

                try:
                    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=30.0)) as client:
                        response = await client.post(
                            current_url,
                            json=envelope,
                            headers=headers,
                        )

                        # Success
                        if response.status_code < 400:
                            return response

                        # Rate limited - extract retry delay and wait
                        if response.status_code == 429:
                            error_data = {}
                            try:
                                error_data = response.json()
                            except Exception:
                                pass

                            error_msg = error_data.get('error', {}).get('message', 'Rate limited')

                            # Try to parse retry delay from response
                            retry_delay = parse_retry_delay(error_msg)
                            if retry_delay is None:
                                # Check retry-after header
                                retry_after = response.headers.get('retry-after')
                                if retry_after:
                                    try:
                                        retry_delay = float(retry_after)
                                    except ValueError:
                                        pass

                            # Use parsed delay or exponential backoff
                            wait_time = retry_delay if retry_delay else backoff

                            if attempt < MAX_RETRIES - 1:
                                print(f"Rate limited. Waiting {wait_time:.1f}s before retry (attempt {attempt + 1}/{MAX_RETRIES})...")
                                await asyncio.sleep(wait_time)
                                backoff = min(backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF_SECONDS)
                                break  # Try next attempt
                            else:
                                raise Exception(f"Rate limited after {MAX_RETRIES} retries: {error_msg}")

                        # Other errors
                        if response.status_code >= 400:
                            error_text = response.text
                            try:
                                error_data = response.json()
                                error_text = error_data.get("error", {}).get("message", error_text)
                            except Exception:
                                pass
                            raise Exception(f"API error {response.status_code}: {error_text}")

                except Exception as e:
                    last_error = e
                    if "Rate limited" in str(e) and attempt < MAX_RETRIES - 1:
                        break  # Will retry after the inner loop
                    continue  # Try next endpoint

            else:
                # All endpoints failed for this attempt
                if last_error and "Rate limited" not in str(last_error):
                    raise last_error

        raise last_error or Exception("All endpoints and retries failed")

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        """
        Make a non-streaming request to the model.

        Args:
            messages: List of conversation messages
            model_settings: Optional model settings
            model_request_parameters: Request parameters including tools

        Returns:
            ModelResponse with the model's response
        """
        # Extract tools from request parameters (both function_tools AND output_tools)
        all_tools = []
        if model_request_parameters:
            all_tools.extend(model_request_parameters.function_tools)
            all_tools.extend(model_request_parameters.output_tools)
        tools = all_tools if all_tools else None

        # Check if we need to force tool calling for structured output
        force_tool_calling = bool(
            model_request_parameters
            and model_request_parameters.output_mode == 'tool'
            and tools
        )

        # Convert messages to Antigravity format
        contents, system_instruction, antigravity_tools = messages_to_antigravity(
            messages, tools
        )

        # Make the request
        response = await self._make_request(
            contents=contents,
            system_instruction=system_instruction,
            tools=antigravity_tools,
            stream=False,
            force_tool_calling=force_tool_calling,
        )

        # Parse response
        response_data = response.json()
        parts, usage = antigravity_to_response(response_data, self._model_name)

        return ModelResponse(
            parts=parts,
            model_name=self._model_name,
            usage=usage,
        )

    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> AsyncIterator[ModelResponse]:
        """
        Make a streaming request to the model.

        Yields ModelResponse objects as they arrive.
        """
        await self._provider.initialize()

        # Extract tools from request parameters (both function_tools AND output_tools)
        all_tools = []
        if model_request_parameters:
            all_tools.extend(model_request_parameters.function_tools)
            all_tools.extend(model_request_parameters.output_tools)
        tools = all_tools if all_tools else None

        # Check if we need to force tool calling for structured output
        force_tool_calling = bool(
            model_request_parameters
            and model_request_parameters.output_mode == 'tool'
            and tools
        )

        # Convert messages to Antigravity format
        contents, system_instruction, antigravity_tools = messages_to_antigravity(
            messages, tools
        )

        tokens = await self._provider.get_tokens()
        project_id = tokens.project_id or ANTIGRAVITY_DEFAULT_PROJECT_ID

        # Build request
        request_body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": self._build_generation_config(),
        }

        if system_instruction:
            request_body["systemInstruction"] = system_instruction

        if antigravity_tools:
            request_body["tools"] = antigravity_tools
            # If force_tool_calling is set, configure the model to require tool usage
            if force_tool_calling:
                request_body["toolConfig"] = {
                    "functionCallingConfig": {
                        "mode": "ANY"  # Forces the model to call at least one function
                    }
                }

        envelope: dict[str, Any] = {
            "project": project_id,
            "model": self._model_name,
            "request": request_body,
            "userAgent": "antigravity",
            "requestId": f"agent-{uuid.uuid4().hex[:12]}",
        }

        # Determine endpoint and headers
        endpoint = self._provider.get_endpoint_for_model(self._model_name)
        header_style = self._provider.get_header_style_for_model(self._model_name)

        if header_style == "gemini-cli":
            headers = dict(GEMINI_CLI_HEADERS)
        else:
            headers = dict(ANTIGRAVITY_HEADERS)

        headers["Authorization"] = f"Bearer {tokens.access_token}"
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "text/event-stream"

        url = f"{endpoint}/v1internal:streamGenerateContent?alt=sse"

        # Make streaming request
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=30.0)) as client:
            async with client.stream(
                "POST",
                url,
                json=envelope,
                headers=headers,
            ) as response:
                if response.status_code >= 400:
                    error_text = await response.aread()
                    raise Exception(f"API error {response.status_code}: {error_text.decode()}")

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    event = parse_sse_event(line)
                    if event is None:
                        continue

                    # Extract parts from SSE event
                    resp = event.get("response", event)
                    candidates = resp.get("candidates", [])

                    if candidates:
                        candidate = candidates[0]
                        content = candidate.get("content", {})
                        event_parts = content.get("parts", [])

                        parts: list[TextPart | ToolCallPart] = []
                        for part in event_parts:
                            # Skip thinking blocks
                            if part.get("thought"):
                                continue

                            if "text" in part:
                                parts.append(TextPart(content=part["text"]))

                            elif "functionCall" in part:
                                fc = part["functionCall"]
                                parts.append(
                                    ToolCallPart(
                                        tool_name=fc.get("name", ""),
                                        args=fc.get("args", {}),
                                        tool_call_id=fc.get("id"),
                                    )
                                )

                        if parts:
                            yield ModelResponse(
                                parts=parts,
                                model_name=self._model_name,
                            )


def create_model(
    model_name: AntigravityModelName | str,
    provider: AntigravityProvider | None = None,
    thinking_budget: int | None = None,
    thinking_level: str | None = None,
    max_output_tokens: int | None = None,
    temperature: float | None = None,
) -> AntigravityModel:
    """
    Factory function to create an Antigravity model.

    Args:
        model_name: Name of the model to use
        provider: Optional pre-configured provider
        thinking_budget: Token budget for thinking (Claude models)
        thinking_level: Thinking level for Gemini models ("low", "medium", "high")
        max_output_tokens: Maximum output tokens
        temperature: Sampling temperature

    Returns:
        Configured AntigravityModel instance
    """
    return AntigravityModel(
        model_name=model_name,
        provider=provider or AntigravityProvider(),
        thinking_budget=thinking_budget,
        thinking_level=thinking_level,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )
