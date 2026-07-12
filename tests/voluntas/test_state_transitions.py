import pytest

from voluntas.schemas import (
    DesireSatisfactionResult,
    DesireStatus,
    Intention,
    Plan,
    PlanStatus,
    PlanStep,
)
from voluntas.state_transitions import (
    all_desires_terminal,
    complete_intention_and_update_desire,
    fail_desire_for_intention,
    finalize_current_intention,
    remove_intention,
    replan_desire_for_intention,
)


def test_remove_intention_only_removes_active_commitment(stub_agent) -> None:
    active = stub_agent.set_current_intention(
        desire_id="active", step_descriptions=["work"]
    )
    other = Intention(
        desire_id="other", active_plan=Plan(steps=[PlanStep(description="other")])
    )

    assert remove_intention(stub_agent, other) == "missing"
    assert stub_agent.active_intention is active
    assert remove_intention(stub_agent, active) == "current"
    assert stub_agent.active_intention is None


@pytest.mark.asyncio
async def test_satisfied_desire_releases_active_intention(stub_agent) -> None:
    desire = stub_agent.add_desire(
        desire_id="done", description="finish", status=DesireStatus.ACTIVE
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id, step_descriptions=["final step"]
    )
    stub_agent.queue_run_output(DesireSatisfactionResult(satisfied=True))

    satisfied = await complete_intention_and_update_desire(stub_agent, intention)

    assert satisfied is True
    assert desire.status is DesireStatus.ACHIEVED
    assert stub_agent.active_intention is None


@pytest.mark.asyncio
async def test_unsatisfied_completed_plan_retains_commitment_for_repair(stub_agent) -> None:
    desire = stub_agent.add_desire(
        desire_id="unfinished", description="finish", status=DesireStatus.ACTIVE
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id, step_descriptions=["attempt"]
    )
    stub_agent.queue_run_output(DesireSatisfactionResult(satisfied=False))

    satisfied = await complete_intention_and_update_desire(stub_agent, intention)

    assert satisfied is False
    assert desire.status is DesireStatus.ACTIVE
    assert stub_agent.active_intention is intention
    assert intention.active_plan.status is PlanStatus.FAILED


def test_replan_releases_commitment_and_returns_desire_to_pending(stub_agent) -> None:
    desire = stub_agent.add_desire(
        desire_id="replan", description="retry", status=DesireStatus.ACTIVE
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id, step_descriptions=["bad route"]
    )

    replan_desire_for_intention(stub_agent, intention, reason="replace commitment")

    assert intention.active_plan.status is PlanStatus.FAILED
    assert desire.status is DesireStatus.PENDING
    assert stub_agent.active_intention is None


def test_fail_and_finalize_release_matching_active_intention(stub_agent) -> None:
    failed_desire = stub_agent.add_desire(
        desire_id="fail", description="impossible", status=DesireStatus.ACTIVE
    )
    failed = stub_agent.set_current_intention(
        desire_id=failed_desire.id, step_descriptions=["try"]
    )
    fail_desire_for_intention(stub_agent, failed, reason="impossible")
    assert failed_desire.status is DesireStatus.FAILED
    assert stub_agent.active_intention is None

    done_desire = stub_agent.add_desire(
        desire_id="final", description="done", status=DesireStatus.ACTIVE
    )
    final = stub_agent.set_current_intention(
        desire_id=done_desire.id, step_descriptions=["finish"]
    )
    finalize_current_intention(
        stub_agent, final, desire_status=DesireStatus.ACHIEVED
    )
    assert done_desire.status is DesireStatus.ACHIEVED
    assert stub_agent.active_intention is None
    assert all_desires_terminal(stub_agent) is True
