import pytest

from voluntas.monitoring import reconsider_current_intention
from voluntas.schemas import DesireStatus, PlanStatus, PlanStep, ReconsiderResult


@pytest.mark.asyncio
async def test_reconsider_replace_plan_preserves_intention_and_desire_commitment(
    stub_agent,
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_invalid",
        description="Need replanning",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["step one", "step two"],
    )
    plan = intention.active_plan
    plan.add_to_history(plan.steps[0], "useful context", True, {})
    stub_agent.queue_run_output(
        ReconsiderResult(
            action="replace_plan",
            reason="Plan assumptions are outdated",
            plan_steps=[PlanStep(description="replacement step")],
        )
    )

    await reconsider_current_intention(stub_agent)

    assert stub_agent.active_intention is intention
    assert desire.status is DesireStatus.ACTIVE
    assert intention.active_plan.status is PlanStatus.ACTIVE
    assert intention.active_plan.current_step_index == 0
    assert [step.description for step in intention.active_plan.steps] == [
        "replacement step"
    ]
    assert len(intention.active_plan.step_history) == 1
    assert intention.active_plan.step_history[0].result == "useful context"


@pytest.mark.asyncio
async def test_reconsider_repair_plan_preserves_completed_steps_and_history(
    stub_agent,
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_repair",
        description="Need repair",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["completed step", "failed step", "old remaining step"],
        current_step=1,
    )
    plan = intention.active_plan
    plan.current_step_index = 0
    plan.add_to_history(plan.steps[0], "completed result", True, {})
    plan.current_step_index = 1
    plan.add_to_history(plan.steps[1], "failed result", False, {})
    plan.status = PlanStatus.FAILED
    stub_agent.queue_run_output(
        ReconsiderResult(
            action="repair_plan",
            reason="Update failed path",
            plan_steps=[
                PlanStep(description="repaired current step"),
                PlanStep(description="repaired follow-up step"),
            ],
        )
    )

    await reconsider_current_intention(stub_agent)

    assert stub_agent.active_intention is intention
    assert desire.status is DesireStatus.ACTIVE
    assert intention.active_plan.status is PlanStatus.ACTIVE
    assert intention.active_plan.current_step_index == 1
    assert [step.description for step in intention.active_plan.steps] == [
        "completed step",
        "repaired current step",
        "repaired follow-up step",
    ]
    assert [history.result for history in intention.active_plan.step_history] == [
        "completed result",
        "failed result",
    ]


@pytest.mark.asyncio
async def test_reconsider_fail_desire_is_separate_terminal_outcome(stub_agent) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_impossible",
        description="Impossible work",
        status=DesireStatus.ACTIVE,
    )
    stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["step one"],
    )
    stub_agent.queue_run_output(
        ReconsiderResult(action="fail_desire", reason="Committed goal is impossible")
    )

    await reconsider_current_intention(stub_agent)

    assert stub_agent.active_intention is None
    assert desire.status is DesireStatus.FAILED


@pytest.mark.asyncio
async def test_reconsider_valid_plan_keeps_current_intention(stub_agent) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_valid",
        description="Still valid",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["step one", "step two"],
    )
    stub_agent.queue_run_output(
        ReconsiderResult(action="continue", reason="Plan remains sound")
    )

    await reconsider_current_intention(stub_agent)

    assert stub_agent.active_intention is intention
    assert desire.status is DesireStatus.ACTIVE
