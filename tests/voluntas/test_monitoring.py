from types import SimpleNamespace

import pytest

import voluntas.monitoring as monitoring
from voluntas.schemas import DesireStatus, PlanStatus, PlanStep, ReconsiderResult


def test_generate_history_context_includes_details_when_requested(stub_agent) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_history",
        description="History formatting",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["first step", "second step"],
    )
    plan = intention.active_plan
    plan.add_to_history(
        plan.steps[0],
        "first result",
        True,
        {"repo_path": {"value": "/tmp/repo", "certainty": 0.9}},
    )
    plan.current_step_index = 1
    plan.add_to_history(plan.steps[1], "second result", False, {})

    history = monitoring.generate_history_context(
        intention,
        max_history=1,
        include_details=True,
    )

    assert "Plan Step 2: second step - Failed" in history
    assert "Result: second result" in history
    assert "Timestamp:" in history
    assert "first step" not in history


def test_format_steps_reports_empty_plan_steps() -> None:
    assert monitoring._format_steps([]) == "  No Plan Steps."


@pytest.mark.asyncio
async def test_reconsider_returns_without_intentions(stub_agent) -> None:
    stub_agent.verbose = True

    await monitoring.reconsider_current_intention(stub_agent)

    assert stub_agent.run_calls == []


@pytest.mark.asyncio
async def test_reconsider_repairs_completed_unsatisfied_plan(stub_agent) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_complete",
        description="Already complete",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["done"],
    )
    intention.active_plan.current_step_index = len(intention.active_plan.steps)
    stub_agent.queue_run_output(
        ReconsiderResult(
            action="replace_plan",
            reason="more work required",
            plan_steps=[PlanStep(description="finish remaining work")],
        )
    )

    await monitoring.reconsider_current_intention(stub_agent)

    assert len(stub_agent.run_calls) == 1
    assert stub_agent.active_intention is intention
    assert intention.active_plan.current_step().description == "finish remaining work"


@pytest.mark.asyncio
async def test_reconsider_continues_when_llm_returns_no_structured_result(
    stub_agent,
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_continue",
        description="Continue safely",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["remaining step"],
    )
    intention.active_plan.status = PlanStatus.FAILED
    stub_agent.queue_run_output(None)

    await monitoring.reconsider_current_intention(stub_agent)

    assert intention.active_plan.status is PlanStatus.ACTIVE
    assert stub_agent.active_intention is intention
    assert desire.status is DesireStatus.ACTIVE


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["repair_plan", "replace_plan"])
async def test_reconsider_replans_when_repair_or_replace_has_no_plan_steps(
    stub_agent,
    action,
) -> None:
    desire = stub_agent.add_desire(
        desire_id=f"desire_{action}",
        description="Needs replanning",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["stale step"],
    )
    stub_agent.queue_run_output(
        ReconsiderResult(action=action, reason="no usable steps", plan_steps=[])
    )

    await monitoring.reconsider_current_intention(stub_agent)

    assert stub_agent.active_intention is None
    assert desire.status is DesireStatus.PENDING
    assert intention.active_plan.status is PlanStatus.FAILED


@pytest.mark.asyncio
async def test_reconsider_unknown_action_replans_conservatively(stub_agent) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_unknown",
        description="Unknown action",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["current step"],
    )
    stub_agent.queue_run_output(
        SimpleNamespace(
            action="pause_until_tomorrow",
            reason="unsupported action",
            plan_steps=None,
        )
    )

    await monitoring.reconsider_current_intention(stub_agent)

    assert stub_agent.active_intention is None
    assert desire.status is DesireStatus.PENDING
    assert intention.active_plan.status is PlanStatus.FAILED


@pytest.mark.asyncio
async def test_reconsider_exception_keeps_plan_available_for_next_cycle(
    monkeypatch,
    stub_agent,
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_exception",
        description="Exception fallback",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["current step"],
    )

    async def raising_run(*_args, **_kwargs):
        raise RuntimeError("reconsideration unavailable")

    monkeypatch.setattr(stub_agent, "run", raising_run)

    await monitoring.reconsider_current_intention(stub_agent)

    assert stub_agent.active_intention is intention
    assert desire.status is DesireStatus.ACTIVE
    assert intention.active_plan.status is PlanStatus.ACTIVE


@pytest.mark.asyncio
async def test_reconsider_repairs_remaining_steps_and_preserves_history(
    stub_agent,
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_repair",
        description="Repair work",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["completed", "old remaining"],
        current_step=1,
    )
    plan = intention.active_plan
    plan.current_step_index = 0
    plan.add_to_history(plan.steps[0], "done", True, {})
    plan.current_step_index = 1
    plan.status = PlanStatus.FAILED
    stub_agent.queue_run_output(
        ReconsiderResult(
            action="repair_plan",
            reason="better route",
            plan_steps=[PlanStep(description="repaired step")],
        )
    )

    await monitoring.reconsider_current_intention(stub_agent)

    assert stub_agent.active_intention is intention
    assert [step.description for step in plan.steps] == ["completed", "repaired step"]
    assert plan.current_step_index == 1
    assert plan.status is PlanStatus.ACTIVE
    assert len(plan.step_history) == 1
