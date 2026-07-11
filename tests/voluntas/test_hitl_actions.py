from types import SimpleNamespace

import pytest

from voluntas.hitl import apply_user_guided_action, build_failure_context
from voluntas.schemas import (
    DesireSatisfactionResult,
    DesireStatus,
    PlanManipulationDirective,
    PlanStatus,
)


def test_failure_context_describes_active_plan_and_current_plan_step(stub_agent) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_context", description="Context test", status=DesireStatus.ACTIVE
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["done step", "failed step", "future step"],
        current_step=1,
    )
    failed_step = intention.active_plan.current_step()

    context = build_failure_context(
        stub_agent,
        intention,
        failed_step,
        SimpleNamespace(output="failed output"),
    )

    assert context["active_plan"] == {
        "status": PlanStatus.ACTIVE.value,
        "current_step_index": 1,
        "total_steps": 3,
        "steps": [step.model_dump() for step in intention.active_plan.steps],
    }
    assert context["current_plan_step"] == failed_step.model_dump()
    assert context["failed_step_description"] == "failed step"
    assert context["remaining_plan_steps"] == [
        intention.active_plan.steps[2].model_dump()
    ]


@pytest.mark.asyncio
async def test_skip_current_step_completes_intention(stub_agent) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_skip", description="Skip test", status=DesireStatus.ACTIVE
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id, step_descriptions=["single step"]
    )

    directive = PlanManipulationDirective(
        manipulation_type="SKIP_CURRENT_STEP",
        user_guidance_summary="Skip this step",
    )
    stub_agent.queue_run_output(
        DesireSatisfactionResult(satisfied=True, reason="Skipped step satisfies desire")
    )

    applied_successfully, beliefs_updated = await apply_user_guided_action(
        stub_agent, directive, intention
    )

    assert applied_successfully is True
    assert beliefs_updated is False
    assert len(stub_agent.intentions) == 0
    assert desire.status is DesireStatus.ACHIEVED


@pytest.mark.asyncio
async def test_abort_intention_requeues_desire(stub_agent) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_abort", description="Abort test", status=DesireStatus.ACTIVE
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id, step_descriptions=["step one", "step two"]
    )

    directive = PlanManipulationDirective(
        manipulation_type="ABORT_INTENTION",
        user_guidance_summary="Abort and re-plan",
    )

    applied_successfully, beliefs_updated = await apply_user_guided_action(
        stub_agent, directive, intention
    )

    assert applied_successfully is True
    assert beliefs_updated is False
    assert len(stub_agent.intentions) == 0
    assert desire.status is DesireStatus.PENDING


@pytest.mark.asyncio
async def test_update_beliefs_and_retry_applies_belief_updates(stub_agent) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_belief", description="Belief update", status=DesireStatus.ACTIVE
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id, step_descriptions=["step one"]
    )

    directive = PlanManipulationDirective(
        manipulation_type="UPDATE_BELIEFS_AND_RETRY",
        user_guidance_summary="Repo path is now known",
        beliefs_to_update={"repo_path": {"value": "/tmp/repo"}},
    )

    applied_successfully, beliefs_updated = await apply_user_guided_action(
        stub_agent, directive, intention
    )

    belief = stub_agent.beliefs.get("repo_path")
    assert applied_successfully is True
    assert beliefs_updated is True
    assert belief is not None
    assert belief.value == "/tmp/repo"
    assert belief.source == "human_guidance"
    assert stub_agent.intentions[0] is intention


@pytest.mark.asyncio
async def test_modify_current_step_updates_current_plan_step(stub_agent) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_modify", description="Modify test", status=DesireStatus.ACTIVE
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["old step", "next step"],
    )
    original_step = intention.active_plan.current_step()
    directive = PlanManipulationDirective(
        manipulation_type="MODIFY_CURRENT_AND_RETRY",
        user_guidance_summary="Use a tool instead",
        current_step_modifications={
            "description": "new step",
            "is_tool_call": True,
            "tool_name": "search",
            "tool_params": {"query": "status"},
        },
    )

    applied_successfully, beliefs_updated = await apply_user_guided_action(
        stub_agent, directive, intention
    )

    current_step = intention.active_plan.current_step()
    assert applied_successfully is True
    assert beliefs_updated is False
    assert current_step is not original_step
    assert current_step.description == "new step"
    assert current_step.is_tool_call is True
    assert current_step.tool_name == "search"
    assert current_step.tool_params == {"query": "status"}
    assert stub_agent.intentions[0] is intention
    assert desire.status is DesireStatus.ACTIVE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("manipulation_type", "expected_steps"),
    [
        (
            "REPLACE_CURRENT_STEP_WITH_NEW",
            ["completed step", "new step", "tail step"],
        ),
        (
            "INSERT_NEW_STEPS_BEFORE_CURRENT",
            ["completed step", "new step", "current step", "tail step"],
        ),
        (
            "INSERT_NEW_STEPS_AFTER_CURRENT",
            ["completed step", "current step", "new step", "tail step"],
        ),
        (
            "REPLACE_REMAINDER_OF_PLAN",
            ["completed step", "new step"],
        ),
    ],
)
async def test_plan_step_list_manipulations_preserve_intention_commitment(
    stub_agent, manipulation_type, expected_steps
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_plan_edit",
        description="Plan edit test",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["completed step", "current step", "tail step"],
        current_step=1,
    )
    intention.active_plan.status = PlanStatus.FAILED
    directive = PlanManipulationDirective(
        manipulation_type=manipulation_type,
        user_guidance_summary="Edit the active plan",
        new_steps_definition=[{"description": "new step"}],
    )

    applied_successfully, beliefs_updated = await apply_user_guided_action(
        stub_agent, directive, intention
    )

    assert applied_successfully is True
    assert beliefs_updated is False
    assert stub_agent.intentions[0] is intention
    assert desire.status is DesireStatus.ACTIVE
    assert intention.active_plan.status is PlanStatus.ACTIVE
    assert intention.active_plan.current_step_index == 1
    assert [step.description for step in intention.active_plan.steps] == expected_steps
