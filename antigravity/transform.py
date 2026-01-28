"""
Message transformation between pydantic-ai and Antigravity API formats.

Antigravity uses a Gemini-style format for all models (including Claude),
which differs from the OpenAI/Anthropic message format that pydantic-ai uses internally.
"""

import json
import re
from typing import Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    UserPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    RetryPromptPart,
    FilePart,
    BinaryContent,
)
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.usage import Usage


def strip_markdown_code_blocks(text: str) -> str:
    """
    Strip markdown code block fences from text.

    Gemini models often wrap JSON in ```json ... ``` blocks,
    which breaks pydantic-ai's JSON parsing for structured output.
    """
    text = text.strip()

    # Handle ```json ... ``` or ``` ... ```
    if text.startswith("```"):
        # Find the end of the first line (may contain language hint)
        first_newline = text.find("\n")
        if first_newline > 0:
            text = text[first_newline + 1:]

        # Remove trailing ```
        if text.endswith("```"):
            text = text[:-3].rstrip()

    return text


def sanitize_tool_name(name: str) -> str:
    """
    Sanitize tool name to comply with Antigravity API requirements.

    Rules:
    - First character must be a letter (a-z, A-Z) or underscore (_)
    - Allowed characters: a-zA-Z0-9, underscores (_), dots (.), colons (:), dashes (-)
    - Max length: 64 characters
    - Slashes (/) are NOT allowed
    """
    # Replace slashes with underscores
    sanitized = name.replace("/", "_")

    # Ensure first character is valid
    if sanitized and not (sanitized[0].isalpha() or sanitized[0] == "_"):
        sanitized = "_" + sanitized

    # Remove any other invalid characters
    sanitized = re.sub(r"[^a-zA-Z0-9_.\:\-]", "_", sanitized)

    # Truncate to 64 characters
    return sanitized[:64]


def transform_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """
    Transform JSON schema to be compatible with Antigravity API.

    Removes unsupported features:
    - const -> enum: [value]
    - $ref, $defs, $schema, $id -> removed
    - default, examples -> removed
    """
    if not isinstance(schema, dict):
        return schema

    result = {}

    for key, value in schema.items():
        # Skip unsupported metadata fields
        if key in ("$ref", "$defs", "definitions", "$schema", "$id", "default", "examples", "title"):
            continue

        # Convert const to enum
        if key == "const":
            result["enum"] = [value]
            continue

        # Convert anyOf/allOf/oneOf to snake_case
        if key == "anyOf":
            result["any_of"] = [transform_schema(v) for v in value]
            continue
        if key == "allOf":
            result["all_of"] = [transform_schema(v) for v in value]
            continue
        if key == "oneOf":
            result["one_of"] = [transform_schema(v) for v in value]
            continue

        # Recursively transform nested objects
        if isinstance(value, dict):
            result[key] = transform_schema(value)
        elif isinstance(value, list):
            result[key] = [
                transform_schema(v) if isinstance(v, dict) else v for v in value
            ]
        else:
            result[key] = value

    return result


def messages_to_antigravity(
    messages: list[ModelMessage],
    tools: list[ToolDefinition] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, list[dict[str, Any]] | None]:
    """
    Convert pydantic-ai messages to Antigravity API format.

    Returns:
        Tuple of (contents, system_instruction, tools)
    """
    contents: list[dict[str, Any]] = []
    system_parts: list[dict[str, Any]] = []

    for message in messages:
        if isinstance(message, ModelRequest):
            # Handle request parts
            user_parts: list[dict[str, Any]] = []

            for part in message.parts:
                if isinstance(part, SystemPromptPart):
                    # System prompts go to systemInstruction
                    system_parts.append({"text": part.content})

                elif isinstance(part, UserPromptPart):
                    # User text message
                    user_parts.append({"text": part.content})

                elif isinstance(part, ToolReturnPart):
                    # Tool result - format as functionResponse
                    response_content = part.content
                    if isinstance(response_content, str):
                        try:
                            response_content = json.loads(response_content)
                        except json.JSONDecodeError:
                            response_content = {"result": response_content}

                    user_parts.append({
                        "functionResponse": {
                            "name": sanitize_tool_name(part.tool_name),
                            "id": part.tool_call_id or "",
                            "response": response_content,
                        }
                    })

                elif isinstance(part, RetryPromptPart):
                    # Retry prompt - treat as user message
                    if isinstance(part.content, str):
                        user_parts.append({"text": f"[Retry] {part.content}"})
                    else:
                        user_parts.append({"text": f"[Retry] {part.content}"})

                elif isinstance(part, FilePart):
                    # File content (images, documents, etc.)
                    content = part.content
                    if isinstance(content, BinaryContent):
                        user_parts.append({
                            "inlineData": {
                                "mimeType": content.media_type,
                                "data": content.base64_data(),
                            }
                        })
                    elif hasattr(content, "url"):
                        # URL-based content
                        media_type = getattr(content, "media_type", "application/octet-stream")
                        user_parts.append({
                            "fileData": {
                                "mimeType": media_type,
                                "fileUri": content.url,
                            }
                        })

            if user_parts:
                contents.append({"role": "user", "parts": user_parts})

        elif isinstance(message, ModelResponse):
            # Handle model response
            model_parts: list[dict[str, Any]] = []

            for part in message.parts:
                if isinstance(part, TextPart):
                    model_parts.append({"text": part.content})

                elif isinstance(part, ToolCallPart):
                    # Tool call - format as functionCall
                    args = part.args
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {"input": args}

                    model_parts.append({
                        "functionCall": {
                            "name": sanitize_tool_name(part.tool_name),
                            "args": args,
                            "id": part.tool_call_id or "",
                        }
                    })

            if model_parts:
                contents.append({"role": "model", "parts": model_parts})

    # Build system instruction if we have system parts
    system_instruction = None
    if system_parts:
        system_instruction = {"parts": system_parts}

    # Transform tools to Antigravity format
    antigravity_tools = None
    if tools:
        function_declarations = []
        for tool in tools:
            # Get parameters schema
            params_schema = tool.parameters_json_schema or {}
            transformed_schema = transform_schema(params_schema)

            function_declarations.append({
                "name": sanitize_tool_name(tool.name),
                "description": tool.description or "",
                "parameters": transformed_schema,
            })

        antigravity_tools = [{"functionDeclarations": function_declarations}]

    return contents, system_instruction, antigravity_tools


def antigravity_to_response(
    response_data: dict[str, Any],
    model_name: str,
) -> tuple[list[TextPart | ToolCallPart], Usage, bool]:
    """
    Convert Antigravity API response to pydantic-ai format.

    Returns:
        Tuple of (parts, usage)
    """
    parts: list[TextPart | ToolCallPart] = []

    # Extract candidates
    response = response_data.get("response", response_data)
    candidates = response.get("candidates", [])

    if candidates:
        candidate = candidates[0]
        content = candidate.get("content", {})
        response_parts = content.get("parts", [])

        for part in response_parts:
            # Text content
            if "text" in part:
                # Skip thinking blocks (they have thought: true)
                if part.get("thought"):
                    continue
                # Strip markdown code blocks that Gemini often adds
                text_content = strip_markdown_code_blocks(part["text"])
                parts.append(TextPart(content=text_content))

            # Function call
            elif "functionCall" in part:
                fc = part["functionCall"]
                parts.append(
                    ToolCallPart(
                        tool_name=fc.get("name", ""),
                        args=fc.get("args", {}),
                        tool_call_id=fc.get("id"),
                    )
                )

    # Extract usage metadata
    usage_meta = response.get("usageMetadata") or {}
    usage_available = False
    if isinstance(usage_meta, dict):
        usage_available = (
            "promptTokenCount" in usage_meta
            or "candidatesTokenCount" in usage_meta
        )

    usage = Usage(
        input_tokens=usage_meta.get("promptTokenCount", 0),
        output_tokens=usage_meta.get("candidatesTokenCount", 0),
        requests=1,
    )

    return parts, usage, usage_available


def parse_sse_event(line: str) -> dict[str, Any] | None:
    """Parse a Server-Sent Events data line."""
    if not line.startswith("data: "):
        return None

    data = line[6:]  # Remove "data: " prefix
    if not data or data == "[DONE]":
        return None

    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return None
