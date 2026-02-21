import pytest

from bdi.hitl import apply_user_guided_action
from bdi.schemas import DesireStatus, PlanManipulationDirective


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
