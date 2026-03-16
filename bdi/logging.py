"""Logging and state formatting utilities for the BDI agent.

This module provides functions for:
- mirroring terminal output to a log file
- formatting beliefs, desires, and intentions for display or LLM prompts
- transforming agent runs into structured JSON log entries
"""

from collections.abc import Sequence
from datetime import datetime
from dataclasses import asdict, is_dataclass
from typing import TYPE_CHECKING, Any, Literal, Optional
import atexit
import json
import os
import re
import sys
import threading

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
    UserContent,
    UserPromptPart,
)

from helper.util import bcolors

if TYPE_CHECKING:
    from bdi.agent import BDI


_ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


class _TerminalMirrorStream:
    """Mirror a terminal stream to a file handle."""

    def __init__(
        self,
        terminal_stream,
        log_file,
        *,
        strip_ansi: bool,
        write_lock: threading.Lock,
    ):
        self._terminal_stream = terminal_stream
        self._log_file = log_file
        self._strip_ansi = strip_ansi
        self._write_lock = write_lock

    def write(self, data: str) -> int:
        if not isinstance(data, str):
            data = str(data)

        written = self._terminal_stream.write(data)

        if data:
            log_data = _ANSI_ESCAPE_RE.sub("", data) if self._strip_ansi else data
            with self._write_lock:
                self._log_file.write(log_data)
                self._log_file.flush()

        return written

    def flush(self) -> None:
        self._terminal_stream.flush()
        with self._write_lock:
            self._log_file.flush()

    def isatty(self) -> bool:
        return self._terminal_stream.isatty()

    def fileno(self) -> int:
        return self._terminal_stream.fileno()

    def __getattr__(self, name):
        return getattr(self._terminal_stream, name)


class _TerminalMirrorState:
    """Runtime state for active stdout/stderr mirroring."""

    def __init__(
        self,
        *,
        log_file_path: str,
        log_file,
        original_stdout,
        original_stderr,
    ):
        self.log_file_path = log_file_path
        self.log_file = log_file
        self.original_stdout = original_stdout
        self.original_stderr = original_stderr


_terminal_mirror_state: Optional[_TerminalMirrorState] = None
_terminal_mirror_state_lock = threading.RLock()


def configure_terminal_output_mirror(
    log_file_path: str,
    *,
    strip_ansi: bool = True,
) -> None:
    """Mirror terminal stdout/stderr output into a log file.

    If mirroring is already active for the same path, this is a no-op.
    If mirroring is active for a different path, the previous mirror is replaced.
    """
    global _terminal_mirror_state

    if not log_file_path:
        return

    normalized_path = os.path.abspath(log_file_path)

    with _terminal_mirror_state_lock:
        if (
            _terminal_mirror_state
            and _terminal_mirror_state.log_file_path == normalized_path
        ):
            return

        if _terminal_mirror_state:
            disable_terminal_output_mirror()

        log_file = open(normalized_path, "a", encoding="utf-8")
        write_lock = threading.Lock()

        original_stdout = sys.stdout
        original_stderr = sys.stderr

        sys.stdout = _TerminalMirrorStream(
            original_stdout,
            log_file,
            strip_ansi=strip_ansi,
            write_lock=write_lock,
        )
        sys.stderr = _TerminalMirrorStream(
            original_stderr,
            log_file,
            strip_ansi=strip_ansi,
            write_lock=write_lock,
        )

        _terminal_mirror_state = _TerminalMirrorState(
            log_file_path=normalized_path,
            log_file=log_file,
            original_stdout=original_stdout,
            original_stderr=original_stderr,
        )


def disable_terminal_output_mirror() -> None:
    """Disable active terminal output mirroring and restore streams."""
    global _terminal_mirror_state

    with _terminal_mirror_state_lock:
        if not _terminal_mirror_state:
            return

        state = _terminal_mirror_state
        _terminal_mirror_state = None

        sys.stdout = state.original_stdout
        sys.stderr = state.original_stderr

        try:
            state.log_file.flush()
        finally:
            state.log_file.close()


atexit.register(disable_terminal_output_mirror)


def _to_jsonable(value: Any) -> Any:
    """Convert arbitrary values into JSON-compatible structures."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, (bytes, bytearray)):
        return value.decode(errors="replace")

    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}

    if isinstance(value, (list, tuple, set, frozenset)):
        return [_to_jsonable(item) for item in value]

    if is_dataclass(value):
        return _to_jsonable(asdict(value))

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _to_jsonable(model_dump(mode="json"))
        except TypeError:
            return _to_jsonable(model_dump())

    dict_method = getattr(value, "dict", None)
    if callable(dict_method):
        return _to_jsonable(dict_method())

    if hasattr(value, "__dict__"):
        public_attrs = {
            key: _to_jsonable(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
        if public_attrs:
            return public_attrs

    return str(value)


def _serialize_value_to_string(value: Any) -> str:
    """Return a stable string representation for structured log fields."""
    if isinstance(value, str):
        return value
    return json.dumps(_to_jsonable(value), ensure_ascii=False)


def _extract_text_from_user_content(content: str | Sequence[UserContent]) -> list[str]:
    if isinstance(content, str):
        return [content]

    return [item for item in content if isinstance(item, str)]


def _extract_user_text_from_messages(messages: Sequence[Any]) -> str:
    fragments: list[str] = []

    for message in messages:
        if not isinstance(message, ModelRequest):
            continue

        for part in message.parts:
            if isinstance(part, UserPromptPart):
                fragments.extend(_extract_text_from_user_content(part.content))

    return "\n".join(fragment for fragment in fragments if fragment)


def _normalize_tool_args(args: Any) -> dict[str, Any]:
    """Ensure tool arguments always serialize as an object."""
    if args is None:
        return {}

    if isinstance(args, dict):
        return {str(key): _to_jsonable(value) for key, value in args.items()}

    if isinstance(args, str):
        try:
            parsed_args = json.loads(args)
        except json.JSONDecodeError:
            return {"input": args}

        if isinstance(parsed_args, dict):
            return {str(key): _to_jsonable(value) for key, value in parsed_args.items()}

        return {"input": _to_jsonable(parsed_args)}

    return {"input": _to_jsonable(args)}


def build_structured_run_log_entry(
    user_prompt: str | Sequence[UserContent] | None,
    result: Any,
) -> dict[str, Any]:
    """Build a structured JSON log entry for a single agent run."""
    messages = result.new_messages() if hasattr(result, "new_messages") else []

    if isinstance(user_prompt, str):
        user_text = user_prompt
    else:
        user_text = _extract_user_text_from_messages(messages)

    assistant_text: str | None = None
    try:
        response = result.response
    except Exception:
        response = None

    if isinstance(response, ModelResponse):
        assistant_text = response.text

    if assistant_text is None:
        assistant_text = _serialize_value_to_string(getattr(result, "output", ""))

    output_tool_name = getattr(result, "_output_tool_name", None)
    tool_returns: dict[str, ToolReturnPart] = {}
    for message in messages:
        if not isinstance(message, ModelRequest):
            continue

        for part in message.parts:
            if not isinstance(part, ToolReturnPart):
                continue
            if output_tool_name and part.tool_name == output_tool_name:
                continue
            tool_returns[part.tool_call_id] = part

    tool_calls: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, ModelResponse):
            continue

        for part in message.parts:
            if not isinstance(part, ToolCallPart):
                continue
            if output_tool_name and part.tool_name == output_tool_name:
                continue

            tool_return = tool_returns.get(part.tool_call_id)
            tool_calls.append(
                {
                    "func_name": part.tool_name,
                    "args": _normalize_tool_args(part.args),
                    "result": _serialize_value_to_string(
                        tool_return.content if tool_return is not None else ""
                    ),
                }
            )

    return {
        "user": user_text,
        "assistant": assistant_text,
        "tool_calls": tool_calls,
    }


def format_beliefs_for_context(agent: "BDI") -> str:
    """Format current beliefs for inclusion in LLM prompts.

    Args:
        agent: The BDI agent instance

    Returns:
        Formatted string containing all beliefs with their values and certainty
    """
    if not agent.beliefs.beliefs:
        return "No beliefs recorded yet."

    beliefs_lines = []
    for name, belief in agent.beliefs.beliefs.items():
        beliefs_lines.append(
            f"- {name}: {belief.value} (Certainty: {belief.certainty:.2f})"
        )
    return "\n".join(beliefs_lines)


def log_states(
    agent: "BDI",
    types: list[Literal["beliefs", "desires", "intentions"]],
    message: str | None = None,
) -> None:
    """Log current agent state to the terminal.

    Args:
        agent: The BDI agent instance
        types: List of state types to log (beliefs, desires, intentions)
        message: Optional message to display with the state
    """
    if message:
        print(f"{bcolors.SYSTEM}{message}{bcolors.ENDC}")

    if "beliefs" in types:
        if agent.verbose:
            belief_str = "\n".join(
                [
                    f"  - {name}: {b.value} (Source: {b.source}, Certainty: {b.certainty:.2f}, Time: {datetime.fromtimestamp(b.timestamp).isoformat()})"
                    for name, b in agent.beliefs.beliefs.items()
                ]
            )
            print(f"{bcolors.BELIEF}Beliefs:\n{belief_str or '  (None)'}{bcolors.ENDC}")
        else:
            print(
                f"{bcolors.BELIEF}Beliefs: {len(agent.beliefs.beliefs)} items{bcolors.ENDC}"
            )

    if "desires" in types:
        if agent.verbose:
            desire_str = "\n".join(
                [
                    f"  - {d.id}: {d.description} (Status: {d.status.value}, Priority: {d.priority})"
                    for d in agent.desires
                ]
            )
            print(f"{bcolors.DESIRE}Desires:\n{desire_str or '  (None)'}{bcolors.ENDC}")
        else:
            print(f"{bcolors.DESIRE}Desires: {len(agent.desires)} items{bcolors.ENDC}")

    if "intentions" in types:
        if agent.verbose:
            intention_str = "\n".join(
                [
                    f"  - Desire '{i.desire_id}': Next -> {i.steps[i.current_step].description if i.current_step < len(i.steps) else '(Completed)'} (Step {i.current_step + 1}/{len(i.steps)})"
                    for i in agent.intentions
                ]
            )
            print(
                f"{bcolors.INTENTION}Intentions:\n{intention_str or '  (None)'}{bcolors.ENDC}"
            )
        else:
            print(
                f"{bcolors.INTENTION}Intentions: {len(agent.intentions)} items{bcolors.ENDC}"
            )


__all__ = [
    "build_structured_run_log_entry",
    "configure_terminal_output_mirror",
    "disable_terminal_output_mirror",
    "format_beliefs_for_context",
    "log_states",
]
