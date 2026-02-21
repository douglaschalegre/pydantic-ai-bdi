import pytest

import bdi.execution as execution
from bdi.schemas import DesireStatus


@pytest.mark.asyncio
async def test_execute_intentions_no_intentions_returns_default(stub_agent) -> None:
    result = await execution.execute_intentions(stub_agent)

    assert result == {"hitl_modified_plan": False, "hitl_updated_beliefs": False}


@pytest.mark.asyncio
async def test_execute_intentions_completed_intention_finalizes_desire(stub_agent) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_done",
        description="Already complete",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["step one"],
    )
    intention.current_step = len(intention.steps)

    result = await execution.execute_intentions(stub_agent)

    assert result == {"hitl_modified_plan": False, "hitl_updated_beliefs": False}
    assert desire.status is DesireStatus.ACHIEVED
    assert len(stub_agent.intentions) == 0


@pytest.mark.asyncio
async def test_execute_intentions_exception_marks_failed(monkeypatch, stub_agent) -> None:
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
    assert desire.status is DesireStatus.FAILED
    assert len(stub_agent.intentions) == 0
    assert len(intention.step_history) == 1
    assert intention.step_history[0].success is False
    assert intention.step_history[0].result == "Exception: boom"


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

    result = await execution.execute_intentions(stub_agent)

    assert result == {"hitl_modified_plan": False, "hitl_updated_beliefs": False}
    assert desire.status is DesireStatus.ACHIEVED
    assert len(stub_agent.intentions) == 0
    assert len(intention.step_history) == 1
    assert intention.step_history[0].success is True
    assert intention.step_history[0].result == "done"
