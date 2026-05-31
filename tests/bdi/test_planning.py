import pytest

from bdi.planning import generate_intentions_from_desires
from bdi.schemas import DesireStatus, HighLevelIntention, HighLevelIntentionList


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

    await generate_intentions_from_desires(stub_agent)

    assert len(stub_agent.intentions) == 1
    intention = stub_agent.intentions[0]
    assert intention.desire_id == active_desire.id
    assert intention.description == "Generate report"
    assert [step.description for step in intention.steps] == ["Generate report"]
    assert stub_agent.run_calls == []


@pytest.mark.asyncio
async def test_stage1_generation_creates_single_step_high_level_intentions(
    stub_agent,
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_1",
        description="Deliver report",
        status=DesireStatus.PENDING,
    )
    stub_agent.queue_run_output(
        HighLevelIntentionList(
            intentions=[
                HighLevelIntention(
                    desire_id=desire.id,
                    description="Collect data",
                ),
                HighLevelIntention(
                    desire_id=desire.id,
                    description="Summarize findings",
                ),
            ]
        )
    )

    await generate_intentions_from_desires(stub_agent)

    assert [call["output_type"] for call in stub_agent.run_calls] == [
        HighLevelIntentionList
    ]
    assert len(stub_agent.intentions) == 2
    assert [intention.description for intention in stub_agent.intentions] == [
        "Collect data",
        "Summarize findings",
    ]
    assert [len(intention.steps) for intention in stub_agent.intentions] == [1, 1]
    assert [intention.steps[0].description for intention in stub_agent.intentions] == [
        "Collect data",
        "Summarize findings",
    ]
    assert desire.status is DesireStatus.ACTIVE


@pytest.mark.asyncio
async def test_planning_deduplicates_high_level_intentions(stub_agent) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_1",
        description="Deliver report",
        status=DesireStatus.ACTIVE,
    )
    stub_agent.queue_run_output(
        HighLevelIntentionList(
            intentions=[
                HighLevelIntention(
                    desire_id=desire.id,
                    description="Collect data",
                ),
                HighLevelIntention(
                    desire_id=desire.id,
                    description="  collect   data  ",
                ),
            ]
        )
    )

    await generate_intentions_from_desires(stub_agent)

    assert len(stub_agent.intentions) == 1
    assert stub_agent.intentions[0].description == "Collect data"
