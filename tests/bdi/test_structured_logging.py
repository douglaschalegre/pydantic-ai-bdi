import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

import bdi.agent as agent_module
from bdi.agent import BDI
from bdi.logging import build_structured_run_log_entry


def _build_result(
    *,
    messages,
    output,
    response=None,
    output_tool_name=None,
):
    if response is None:
        response = next(
            (message for message in reversed(messages) if isinstance(message, ModelResponse)),
            None,
        )

    return SimpleNamespace(
        output=output,
        response=response,
        new_messages=lambda: list(messages),
        _output_tool_name=output_tool_name,
    )


def test_build_structured_run_log_entry_for_text_response() -> None:
    messages = [
        ModelRequest(parts=[UserPromptPart("Summarize the latest changes.")]),
        ModelResponse(parts=[TextPart(content="The latest changes update the planner.")]),
    ]
    result = _build_result(
        messages=messages,
        output="The latest changes update the planner.",
    )

    entry = build_structured_run_log_entry("Summarize the latest changes.", result)

    assert entry == {
        "user": "Summarize the latest changes.",
        "assistant": "The latest changes update the planner.",
        "tool_calls": [],
    }


def test_build_structured_run_log_entry_for_structured_output_filters_output_tool() -> None:
    class StructuredAnswer(BaseModel):
        summary: str

    messages = [
        ModelRequest(parts=[UserPromptPart("Return a structured summary.")]),
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="final_result",
                    args={"summary": "Planner updated"},
                    tool_call_id="output_1",
                )
            ]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="final_result",
                    content={"summary": "Planner updated"},
                    tool_call_id="output_1",
                )
            ]
        ),
        ModelResponse(parts=[]),
    ]
    result = _build_result(
        messages=messages,
        output=StructuredAnswer(summary="Planner updated"),
        response=messages[-1],
        output_tool_name="final_result",
    )

    entry = build_structured_run_log_entry(None, result)

    assert entry == {
        "user": "Return a structured summary.",
        "assistant": '{"summary": "Planner updated"}',
        "tool_calls": [],
    }


def test_build_structured_run_log_entry_for_tool_calls_preserves_order() -> None:
    messages = [
        ModelRequest(parts=[UserPromptPart("Use the tools and report back.")]),
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="execute_code",
                    args='{"code": "print(1)"}',
                    tool_call_id="call_1",
                ),
                ToolCallPart(
                    tool_name="browse",
                    args="https://example.com",
                    tool_call_id="call_2",
                ),
            ]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="execute_code",
                    content={"status": "ok"},
                    tool_call_id="call_1",
                ),
                ToolReturnPart(
                    tool_name="browse",
                    content="Loaded example.com",
                    tool_call_id="call_2",
                ),
            ]
        ),
        ModelResponse(parts=[TextPart(content="Finished.")]),
    ]
    result = _build_result(messages=messages, output="Finished.")

    entry = build_structured_run_log_entry(None, result)

    assert entry == {
        "user": "Use the tools and report back.",
        "assistant": "Finished.",
        "tool_calls": [
            {
                "func_name": "execute_code",
                "args": {"code": "print(1)"},
                "result": '{"status": "ok"}',
            },
            {
                "func_name": "browse",
                "args": {"input": "https://example.com"},
                "result": "Loaded example.com",
            },
        ],
    }


@pytest.mark.asyncio
async def test_bdi_run_persists_structured_log_after_each_call(
    tmp_path, monkeypatch
) -> None:
    structured_log_path = tmp_path / "agent-run.json"

    async def fake_run(self, user_prompt=None, **_kwargs):
        assistant_text = f"assistant:{user_prompt}"
        messages = [
            ModelRequest(parts=[UserPromptPart(str(user_prompt))]),
            ModelResponse(parts=[TextPart(content=assistant_text)]),
        ]
        return _build_result(messages=messages, output=assistant_text)

    monkeypatch.setattr(Agent, "run", fake_run)

    agent = BDI(structured_log_file_path=str(structured_log_path))

    assert json.loads(structured_log_path.read_text()) == []

    await agent.run("first")
    assert json.loads(structured_log_path.read_text()) == [
        {
            "user": "first",
            "assistant": "assistant:first",
            "tool_calls": [],
        }
    ]

    await agent.run("second")
    assert json.loads(structured_log_path.read_text()) == [
        {
            "user": "first",
            "assistant": "assistant:first",
            "tool_calls": [],
        },
        {
            "user": "second",
            "assistant": "assistant:second",
            "tool_calls": [],
        },
    ]


def test_bdi_initializes_text_and_structured_logs_independently(
    tmp_path, monkeypatch
) -> None:
    mirrored_paths: list[str] = []

    def fake_configure_terminal_output_mirror(
        log_file_path: str,
        *,
        strip_ansi: bool = True,
    ) -> None:
        assert strip_ansi is True
        mirrored_paths.append(log_file_path)

    monkeypatch.setattr(
        agent_module,
        "configure_terminal_output_mirror",
        fake_configure_terminal_output_mirror,
    )

    text_log_path = tmp_path / "agent.log"
    structured_log_path = tmp_path / "agent-run.json"

    BDI(
        log_file_path=str(text_log_path),
        structured_log_file_path=str(structured_log_path),
    )

    assert mirrored_paths == [str(text_log_path)]
    assert text_log_path.exists()
    assert json.loads(structured_log_path.read_text()) == []
