import pytest

from bdi.planning import generate_intentions_from_desires
from bdi.schemas import (
    DesireStatus,
    HighLevelIntention,
    HighLevelIntentionList,
    PlanStatus,
)


@pytest.mark.asyncio
async def test_explicit_intentions_target_first_pending_desire(stub_agent) -> None:
    stub_agent.add_desire(
        desire_id="desire_done",
        description="Already done",
        status=DesireStatus.ACHIEVED,
    )
    pending_desire = stub_agent.add_desire(
        desire_id="desire_pending",
        description="Needs execution",
        status=DesireStatus.PENDING,
    )
    stub_agent.initial_intention_guidance = ["Generate report", "Send report"]

    await generate_intentions_from_desires(stub_agent)

    assert len(stub_agent.intentions) == 1
    intention = stub_agent.intentions[0]
    assert intention.desire_id == pending_desire.id
    assert intention.description == "Generate report"
    assert intention.active_plan.status is PlanStatus.ACTIVE
    assert [step.description for step in intention.active_plan.steps] == [
        "Generate report"
    ]
    assert stub_agent.run_calls == []
    assert pending_desire.status is DesireStatus.ACTIVE


@pytest.mark.asyncio
async def test_stage1_generation_commits_one_high_level_intention(
    stub_agent,
) -> None:
    selected_desire = stub_agent.add_desire(
        desire_id="desire_1",
        description="Deliver report",
        status=DesireStatus.PENDING,
    )
    unselected_desire = stub_agent.add_desire(
        desire_id="desire_2",
        description="Book travel",
        status=DesireStatus.PENDING,
    )
    stub_agent.queue_run_output(
        HighLevelIntentionList(
            intentions=[
                HighLevelIntention(
                    desire_id=selected_desire.id,
                    description="Collect data",
                ),
                HighLevelIntention(
                    desire_id=unselected_desire.id,
                    description="Find flights",
                ),
            ]
        )
    )

    await generate_intentions_from_desires(stub_agent)

    assert [call["output_type"] for call in stub_agent.run_calls] == [
        HighLevelIntentionList
    ]
    assert len(stub_agent.intentions) == 1
    assert [intention.description for intention in stub_agent.intentions] == [
        "Collect data",
    ]
    assert [
        len(intention.active_plan.steps) for intention in stub_agent.intentions
    ] == [
        1,
    ]
    assert [
        intention.active_plan.steps[0].description
        for intention in stub_agent.intentions
    ] == ["Collect data"]
    assert [intention.active_plan.status for intention in stub_agent.intentions] == [
        PlanStatus.ACTIVE,
    ]
    assert selected_desire.status is DesireStatus.ACTIVE
    assert unselected_desire.status is DesireStatus.PENDING


@pytest.mark.asyncio
async def test_planning_deduplicates_high_level_intentions(stub_agent) -> None:
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
                    description="  collect   data  ",
                ),
            ]
        )
    )

    await generate_intentions_from_desires(stub_agent)

    assert len(stub_agent.intentions) == 1
    assert stub_agent.intentions[0].description == "Collect data"


@pytest.mark.asyncio
async def test_planning_ignores_intentions_for_non_pending_desires(stub_agent) -> None:
    pending_desire = stub_agent.add_desire(
        desire_id="desire_pending",
        description="Pending work",
        status=DesireStatus.PENDING,
    )
    achieved_desire = stub_agent.add_desire(
        desire_id="desire_done",
        description="Done work",
        status=DesireStatus.ACHIEVED,
    )
    stub_agent.queue_run_output(
        HighLevelIntentionList(
            intentions=[
                HighLevelIntention(
                    desire_id=achieved_desire.id,
                    description="Speculative done work",
                ),
                HighLevelIntention(
                    desire_id=pending_desire.id,
                    description="Do pending work",
                ),
            ]
        )
    )

    await generate_intentions_from_desires(stub_agent)

    assert len(stub_agent.intentions) == 1
    assert stub_agent.intentions[0].desire_id == pending_desire.id
    assert stub_agent.intentions[0].description == "Do pending work"
    assert pending_desire.status is DesireStatus.ACTIVE
    assert achieved_desire.status is DesireStatus.ACHIEVED
