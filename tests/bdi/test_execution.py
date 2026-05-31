import pytest
from types import SimpleNamespace
from typing import Any, cast

import bdi.execution as execution
from bdi.schemas import DesireSatisfactionResult, DesireStatus, PlanStatus


@pytest.mark.asyncio
async def test_execute_intentions_no_intentions_returns_default(stub_agent) -> None:
    result = await execution.execute_intentions(stub_agent)

    assert result == {"hitl_modified_plan": False, "hitl_updated_beliefs": False}


@pytest.mark.asyncio
async def test_execute_intentions_completed_intention_finalizes_desire(
    stub_agent,
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_done",
        description="Already complete",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["step one"],
    )
    plan = intention.active_plan
    plan.current_step_index = len(plan.steps)
    stub_agent.queue_run_output(
        DesireSatisfactionResult(satisfied=True, reason="Already complete")
    )

    result = await execution.execute_intentions(stub_agent)

    assert result == {"hitl_modified_plan": False, "hitl_updated_beliefs": False}
    assert desire.status is DesireStatus.ACHIEVED
    assert len(stub_agent.intentions) == 0
    assert plan.status is PlanStatus.COMPLETED


@pytest.mark.asyncio
async def test_execute_intentions_exception_preserves_commitment_for_reconsideration(
    monkeypatch, stub_agent
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_exception",
        description="Exception path",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["step one"],
    )

    async def raising_run(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(stub_agent, "run", raising_run)

    result = await execution.execute_intentions(stub_agent)

    assert result == {"hitl_modified_plan": False, "hitl_updated_beliefs": False}
    assert desire.status is DesireStatus.ACTIVE
    assert len(stub_agent.intentions) == 1
    assert stub_agent.intentions[0] is intention
    assert intention.active_plan.status is PlanStatus.FAILED
    assert len(intention.active_plan.step_history) == 1
    assert intention.active_plan.step_history[0].success is False
    assert intention.active_plan.step_history[0].result == "Exception: boom"


@pytest.mark.asyncio
async def test_execute_intentions_success_completes_single_step(
    monkeypatch, stub_agent
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_success",
        description="Happy path",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["step one"],
    )

    async def always_success(*_args, **_kwargs):
        return True

    monkeypatch.setattr(
        execution,
        "analyze_step_outcome_and_update_beliefs",
        always_success,
    )
    stub_agent.queue_run_output("done")
    stub_agent.queue_run_output(
        DesireSatisfactionResult(satisfied=True, reason="Step completed desire")
    )

    result = await execution.execute_intentions(stub_agent)

    assert result == {"hitl_modified_plan": False, "hitl_updated_beliefs": False}
    assert desire.status is DesireStatus.ACHIEVED
    assert len(stub_agent.intentions) == 0
    assert intention.active_plan.status is PlanStatus.COMPLETED
    assert intention.active_plan.current_step_index == 1
    assert len(intention.active_plan.step_history) == 1
    assert intention.active_plan.step_history[0].success is True
    assert intention.active_plan.step_history[0].result == "done"


def test_extract_latest_tool_result_content_prefers_tool_payload() -> None:
    step_result = SimpleNamespace(
        all_messages=lambda: [
            SimpleNamespace(
                parts=[
                    SimpleNamespace(
                        tool_name="run_in_tac",
                        args={"command": "cat /instruction/task.md"},
                    ),
                    SimpleNamespace(
                        tool_call_id="call_1", content="raw instruction content"
                    ),
                ]
            )
        ]
    )

    extracted = execution._extract_latest_tool_result_content(cast(Any, step_result))
    assert extracted == "raw instruction content"
