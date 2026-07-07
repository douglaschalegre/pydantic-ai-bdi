from collections import deque
from types import SimpleNamespace

import pytest

from bdi.schemas import (
    DesireSatisfactionResult,
    DesireStatus,
    Intention,
    Plan,
    PlanStatus,
    PlanStep,
)
from bdi.state_transitions import (
    all_desires_terminal,
    assess_desire_satisfaction,
    complete_intention_and_update_desire,
    fail_desire_for_intention,
    finalize_current_intention,
    replan_desire_for_intention,
    remove_intention,
    update_desire_status,
)


def test_update_desire_status_updates_matching_desire(stub_agent) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_status",
        description="Status change",
        status=DesireStatus.PENDING,
    )

    found = update_desire_status(stub_agent, desire.id, DesireStatus.ACTIVE)

    assert found is True
    assert desire.status is DesireStatus.ACTIVE


def test_update_desire_status_reports_missing_and_skips_noop(stub_agent) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_status",
        description="Status unchanged",
        status=DesireStatus.PENDING,
    )

    found = update_desire_status(stub_agent, desire.id, DesireStatus.PENDING)

    assert found is True
    assert desire.status is DesireStatus.PENDING
    assert desire.achieved_at is None
    assert update_desire_status(stub_agent, "missing", DesireStatus.ACTIVE) is False


def test_remove_intention_reports_origin(stub_agent) -> None:
    current = Intention(
        desire_id="desire_current",
        active_plan=Plan(steps=[PlanStep(description="current step")]),
    )
    queued = Intention(
        desire_id="desire_queued",
        active_plan=Plan(steps=[PlanStep(description="queued step")]),
    )
    missing = Intention(
        desire_id="desire_missing",
        active_plan=Plan(steps=[PlanStep(description="missing step")]),
    )
    stub_agent.intentions = deque([current, queued])

    assert remove_intention(stub_agent, queued) == "queued"
    assert remove_intention(stub_agent, current) == "current"
    assert remove_intention(stub_agent, missing) == "missing"


def test_all_desires_terminal_requires_desires_and_terminal_statuses(stub_agent) -> None:
    assert all_desires_terminal(stub_agent) is False

    stub_agent.add_desire(
        desire_id="achieved",
        description="Done",
        status=DesireStatus.ACHIEVED,
    )
    stub_agent.add_desire(
        desire_id="failed",
        description="Impossible",
        status=DesireStatus.FAILED,
    )
    assert all_desires_terminal(stub_agent) is True

    stub_agent.add_desire(
        desire_id="pending",
        description="Not done",
        status=DesireStatus.PENDING,
    )
    assert all_desires_terminal(stub_agent) is False


@pytest.mark.asyncio
async def test_assess_desire_satisfaction_builds_prompt_with_history_and_remaining_work(
    stub_agent,
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_assess",
        description="Assess completion",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["completed step"],
    )
    intention.active_plan.add_to_history(
        intention.active_plan.steps[0],
        "step result",
        True,
        {},
    )
    remaining = Intention(
        desire_id=desire.id,
        description="Follow-up intention",
        active_plan=Plan(
            steps=[
                PlanStep(description="already done"),
                PlanStep(description="remaining step"),
            ],
            current_step_index=1,
        ),
    )
    stub_agent.intentions.append(remaining)
    stub_agent.queue_run_output(
        DesireSatisfactionResult(satisfied=True, reason="Enough evidence")
    )

    result = await assess_desire_satisfaction(stub_agent, intention)

    assert result.satisfied is True
    assert stub_agent.run_calls[0]["output_type"] is DesireSatisfactionResult
    prompt = stub_agent.run_calls[0]["prompt"]
    assert "Assess completion" in prompt
    assert "step result" in prompt
    assert "Follow-up intention" in prompt
    assert "remaining step" in prompt


@pytest.mark.asyncio
async def test_assess_desire_satisfaction_handles_missing_output_and_run_errors(
    stub_agent,
) -> None:
    intention = stub_agent.set_current_intention(
        desire_id="unknown_desire",
        step_descriptions=["step one"],
    )
    stub_agent._queued_run_outputs.append(SimpleNamespace(output=None))

    missing = await assess_desire_satisfaction(stub_agent, intention)
    failed = await assess_desire_satisfaction(stub_agent, intention)

    assert missing.satisfied is False
    assert missing.reason == "Desire satisfaction assessment returned no result."
    assert failed.satisfied is False
    assert failed.reason.startswith("Desire satisfaction assessment failed:")


@pytest.mark.asyncio
async def test_complete_intention_marks_desire_achieved_and_clears_related_work(
    stub_agent,
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_done",
        description="Complete goal",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["final step"],
    )
    other_for_desire = Intention(
        desire_id=desire.id,
        active_plan=Plan(steps=[PlanStep(description="obsolete step")]),
    )
    unrelated = Intention(
        desire_id="other_desire",
        active_plan=Plan(steps=[PlanStep(description="unrelated step")]),
    )
    stub_agent.intentions.extend([other_for_desire, unrelated])
    stub_agent.queue_run_output(
        DesireSatisfactionResult(satisfied=True, reason="Goal satisfied")
    )

    await complete_intention_and_update_desire(stub_agent, intention)

    assert desire.status is DesireStatus.ACHIEVED
    assert list(stub_agent.intentions) == [unrelated]


@pytest.mark.asyncio
async def test_complete_intention_keeps_desire_active_when_more_work_remains(
    stub_agent,
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_more_work",
        description="Need follow-up",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["first step"],
    )
    remaining = Intention(
        desire_id=desire.id,
        active_plan=Plan(steps=[PlanStep(description="next step")]),
    )
    stub_agent.intentions.append(remaining)
    stub_agent.queue_run_output(
        DesireSatisfactionResult(satisfied=False, reason="More work required")
    )

    await complete_intention_and_update_desire(stub_agent, intention)

    assert desire.status is DesireStatus.ACTIVE
    assert list(stub_agent.intentions) == [remaining]


@pytest.mark.asyncio
async def test_complete_intention_returns_desire_pending_when_plan_exhausted(
    stub_agent,
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_replan",
        description="Needs replanning",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["only step"],
    )
    stub_agent.queue_run_output(DesireSatisfactionResult(satisfied=False))

    await complete_intention_and_update_desire(stub_agent, intention)

    assert desire.status is DesireStatus.PENDING
    assert len(stub_agent.intentions) == 0


def test_replan_desire_for_intention_fails_plan_and_clears_related_work(
    stub_agent,
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_replan",
        description="Replan",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["bad step"],
    )
    unrelated = Intention(
        desire_id="other_desire",
        active_plan=Plan(steps=[PlanStep(description="keep")]),
    )
    stub_agent.intentions.append(unrelated)

    replan_desire_for_intention(stub_agent, intention, reason="Invalid plan")

    assert intention.active_plan.status is PlanStatus.FAILED
    assert desire.status is DesireStatus.PENDING
    assert list(stub_agent.intentions) == [unrelated]


def test_fail_desire_for_intention_fails_plan_desire_and_related_work(
    stub_agent,
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_fail",
        description="Fail",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["impossible step"],
    )

    fail_desire_for_intention(stub_agent, intention, reason="Impossible")

    assert intention.active_plan.status is PlanStatus.FAILED
    assert desire.status is DesireStatus.FAILED
    assert len(stub_agent.intentions) == 0


def test_finalize_current_intention_updates_status_and_pops_queue(stub_agent) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_finalize",
        description="Finalize",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["step one"],
    )

    finalize_current_intention(
        stub_agent,
        intention,
        desire_status=DesireStatus.ACHIEVED,
    )

    assert desire.status is DesireStatus.ACHIEVED
    assert len(stub_agent.intentions) == 0


def test_finalize_current_intention_can_force_status_update_without_current_match(
    stub_agent,
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_finalize_force",
        description="Force finalize",
        status=DesireStatus.ACHIEVED,
    )
    current = stub_agent.set_current_intention(
        desire_id="other_desire",
        step_descriptions=["current step"],
    )
    not_current = Intention(
        desire_id=desire.id,
        active_plan=Plan(steps=[PlanStep(description="not current")]),
    )

    finalize_current_intention(
        stub_agent,
        not_current,
        desire_status=DesireStatus.ACHIEVED,
        force_status_update=True,
    )

    assert desire.status is DesireStatus.ACHIEVED
    assert desire.achieved_at is not None
    assert list(stub_agent.intentions) == [current]
