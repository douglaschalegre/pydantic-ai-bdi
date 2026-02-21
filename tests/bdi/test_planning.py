import pytest

from bdi.planning import generate_intentions_from_desires
from bdi.schemas import DesireStatus, DetailedStepList, IntentionStep


@pytest.mark.asyncio
async def test_explicit_intentions_target_first_actionable_desire(stub_agent) -> None:
    stub_agent.add_desire(
        desire_id="desire_done",
        description="Already done",
        status=DesireStatus.ACHIEVED,
    )
    active_desire = stub_agent.add_desire(
        desire_id="desire_active",
        description="Needs execution",
        status=DesireStatus.ACTIVE,
    )
    stub_agent.initial_intention_guidance = ["Generate report"]
    stub_agent.queue_run_output(
        DetailedStepList(steps=[IntentionStep(description="Collect inputs")])
    )

    await generate_intentions_from_desires(stub_agent)

    assert len(stub_agent.intentions) == 1
    assert stub_agent.intentions[0].desire_id == active_desire.id
