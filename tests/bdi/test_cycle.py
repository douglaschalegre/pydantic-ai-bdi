import pytest

import bdi.cycle as cycle
import bdi.monitoring as monitoring
from bdi.schemas import DesireStatus, PlanStatus, PlanStep, ReconsiderResult


@pytest.mark.asyncio
async def test_cycle_does_not_plan_pending_desires_while_intention_active(
    monkeypatch,
    stub_agent,
) -> None:
    active_desire = stub_agent.add_desire(
        desire_id="desire_active",
        description="Active work",
        status=DesireStatus.ACTIVE,
    )
    pending_desire = stub_agent.add_desire(
        desire_id="desire_pending",
        description="Pending work",
        status=DesireStatus.PENDING,
    )
    active_intention = stub_agent.set_current_intention(
        desire_id=active_desire.id,
        step_descriptions=["continue active work"],
    )

    async def fail_if_planning_runs(_agent):
        raise AssertionError("planning should not run while an intention is active")

    async def execute_without_finishing(_agent):
        return {"hitl_modified_plan": False, "hitl_updated_beliefs": False}

    async def skip_reconsideration(_agent):
        return None

    monkeypatch.setattr(
        cycle, "generate_intentions_from_desires", fail_if_planning_runs
    )
    monkeypatch.setattr(cycle, "execute_intentions", execute_without_finishing)
    monkeypatch.setattr(cycle, "reconsider_current_intention", skip_reconsideration)

    result = await cycle.bdi_cycle(stub_agent)

    assert result == "executed"
    assert list(stub_agent.intentions) == [active_intention]
    assert active_desire.status is DesireStatus.ACTIVE
    assert pending_desire.status is DesireStatus.PENDING
    assert stub_agent.run_calls == []


@pytest.mark.asyncio
async def test_cycle_skips_reconsideration_after_successful_plan_step(
    monkeypatch,
    stub_agent,
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_progress",
        description="Make progress",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["step one", "step two"],
    )

    async def execute_success(_agent):
        plan = intention.active_plan
        step = plan.steps[plan.current_step_index]
        plan.add_to_history(step, "ok", True, {})
        plan.advance_current_step(lambda **_kwargs: None, desire_id=desire.id)
        return {"hitl_modified_plan": False, "hitl_updated_beliefs": False}

    async def fail_if_reconsideration_runs(_agent):
        raise AssertionError("successful Plan Step progress should not reconsider")

    monkeypatch.setattr(cycle, "execute_intentions", execute_success)
    monkeypatch.setattr(
        cycle, "reconsider_current_intention", fail_if_reconsideration_runs
    )

    result = await cycle.bdi_cycle(stub_agent)

    assert result == "executed"
    assert list(stub_agent.intentions) == [intention]
    assert intention.active_plan.current_step_index == 1


@pytest.mark.asyncio
async def test_cycle_reconsiders_after_failed_plan_step(
    monkeypatch,
    stub_agent,
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_failure",
        description="Recover from failure",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["step one", "step two"],
    )
    reconsidered = False

    async def execute_failure(_agent):
        plan = intention.active_plan
        step = plan.steps[plan.current_step_index]
        plan.add_to_history(step, "failed", False, {})
        plan.status = PlanStatus.FAILED
        return {"hitl_modified_plan": False, "hitl_updated_beliefs": False}

    async def reconsider(_agent):
        nonlocal reconsidered
        reconsidered = True

    monkeypatch.setattr(cycle, "execute_intentions", execute_failure)
    monkeypatch.setattr(cycle, "reconsider_current_intention", reconsider)

    result = await cycle.bdi_cycle(stub_agent)

    assert result == "executed"
    assert reconsidered is True


@pytest.mark.asyncio
async def test_reconsideration_prompt_is_plan_aware_on_failure_path(stub_agent) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_plan",
        description="Use the whole plan",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["completed step", "failed step", "remaining step"],
        current_step=1,
    )
    plan = intention.active_plan
    plan.current_step_index = 0
    plan.add_to_history(plan.steps[0], "completed result", True, {})
    plan.current_step_index = 1
    plan.add_to_history(plan.steps[1], "failure result", False, {})
    stub_agent.beliefs.upsert("known_fact", "current", "test")
    stub_agent.queue_run_output(
        ReconsiderResult(
            action="replace_plan",
            reason="bad assumption",
            plan_steps=[PlanStep(description="replacement step")],
        )
    )

    await monitoring.reconsider_current_intention(stub_agent)

    prompt = stub_agent.run_calls[0]["prompt"]
    assert "Completed Plan Steps" in prompt
    assert "completed step" in prompt
    assert "Relevant Failure History" in prompt
    assert "failure result" in prompt
    assert "Remaining Plan Steps" in prompt
    assert "failed step" in prompt
    assert "remaining step" in prompt
    assert "known_fact: current" in prompt
    assert desire.status is DesireStatus.ACTIVE
    assert len(stub_agent.intentions) == 1
