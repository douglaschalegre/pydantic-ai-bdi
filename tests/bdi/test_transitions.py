import pytest

from bdi.monitoring import reconsider_current_intention
from bdi.schemas import DesireStatus, ReconsiderResult


@pytest.mark.asyncio
async def test_reconsider_invalid_plan_removes_intention_and_requeues_desire(
    stub_agent,
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_invalid",
        description="Need replanning",
        status=DesireStatus.ACTIVE,
    )
    stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["step one", "step two"],
    )
    stub_agent.queue_run_output(
        ReconsiderResult(valid=False, reason="Plan assumptions are outdated")
    )

    await reconsider_current_intention(stub_agent)

    assert len(stub_agent.intentions) == 0
    assert desire.status is DesireStatus.PENDING


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
    stub_agent.queue_run_output(ReconsiderResult(valid=True, reason="Plan remains sound"))

    await reconsider_current_intention(stub_agent)

    assert len(stub_agent.intentions) == 1
    assert stub_agent.intentions[0] is intention
    assert desire.status is DesireStatus.ACTIVE
