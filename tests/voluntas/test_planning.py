import pytest

from voluntas.planning import generate_intentions_from_desires
from voluntas.schemas import DesireStatus, PlanningDecision, PlanStatus


@pytest.mark.asyncio
async def test_explicit_guidance_adopts_first_pending_desire(stub_agent) -> None:
    stub_agent.add_desire(
        desire_id="done", description="Already done", status=DesireStatus.ACHIEVED
    )
    pending = stub_agent.add_desire(
        desire_id="pending", description="Needs execution"
    )
    stub_agent.initial_intention_guidance = ["Generate report", "Send report"]

    await generate_intentions_from_desires(stub_agent)

    intention = stub_agent.active_intention
    assert intention is not None
    assert intention.desire_id == pending.id
    assert intention.description == "Generate report"
    assert intention.active_plan.status is PlanStatus.ACTIVE
    assert [step.description for step in intention.active_plan.steps] == [
        "Generate report"
    ]
    assert stub_agent.run_calls == []
    assert pending.status is DesireStatus.ACTIVE


@pytest.mark.asyncio
async def test_planning_decision_adopts_exactly_one_pending_desire(stub_agent) -> None:
    selected = stub_agent.add_desire(desire_id="report", description="Deliver report")
    unselected = stub_agent.add_desire(desire_id="travel", description="Book travel")
    stub_agent.queue_run_output(
        PlanningDecision(desire_id=selected.id, description="Collect data")
    )

    await generate_intentions_from_desires(stub_agent)

    assert [call["output_type"] for call in stub_agent.run_calls] == [PlanningDecision]
    intention = stub_agent.active_intention
    assert intention is not None
    assert intention.desire_id == selected.id
    assert intention.description == "Collect data"
    assert [step.description for step in intention.active_plan.steps] == ["Collect data"]
    assert selected.status is DesireStatus.ACTIVE
    assert unselected.status is DesireStatus.PENDING


@pytest.mark.asyncio
async def test_planning_rejects_selection_of_non_pending_desire(stub_agent) -> None:
    pending = stub_agent.add_desire(desire_id="pending", description="Pending work")
    achieved = stub_agent.add_desire(
        desire_id="done", description="Done work", status=DesireStatus.ACHIEVED
    )
    stub_agent.queue_run_output(
        PlanningDecision(desire_id=achieved.id, description="Repeat done work")
    )

    await generate_intentions_from_desires(stub_agent)

    assert stub_agent.active_intention is None
    assert pending.status is DesireStatus.PENDING
    assert achieved.status is DesireStatus.ACHIEVED


@pytest.mark.asyncio
async def test_planning_returns_without_desires(stub_agent) -> None:
    await generate_intentions_from_desires(stub_agent)

    assert stub_agent.active_intention is None
    assert stub_agent.run_calls == []


@pytest.mark.asyncio
async def test_planning_returns_when_intention_already_active(stub_agent) -> None:
    desire = stub_agent.add_desire(desire_id="active", description="Active work")
    intention = stub_agent.set_current_intention(
        desire_id=desire.id, step_descriptions=["existing step"]
    )

    await generate_intentions_from_desires(stub_agent)

    assert stub_agent.active_intention is intention
    assert stub_agent.run_calls == []
    assert desire.status is DesireStatus.PENDING


@pytest.mark.asyncio
async def test_planning_returns_without_pending_desires(stub_agent) -> None:
    stub_agent.add_desire(
        desire_id="done", description="Done work", status=DesireStatus.ACHIEVED
    )

    await generate_intentions_from_desires(stub_agent)

    assert stub_agent.active_intention is None
    assert stub_agent.run_calls == []


@pytest.mark.asyncio
async def test_planning_preserves_pending_state_when_output_is_absent(stub_agent) -> None:
    desire = stub_agent.add_desire(desire_id="pending", description="Pending work")
    stub_agent.queue_run_output(None)

    await generate_intentions_from_desires(stub_agent)

    assert stub_agent.active_intention is None
    assert desire.status is DesireStatus.PENDING
    assert len(stub_agent.run_calls) == 1


@pytest.mark.asyncio
async def test_planning_preserves_pending_state_when_model_fails(
    monkeypatch, stub_agent
) -> None:
    desire = stub_agent.add_desire(desire_id="pending", description="Pending work")

    async def raising_run(*_args, **_kwargs):
        raise RuntimeError("planner unavailable")

    monkeypatch.setattr(stub_agent, "run", raising_run)

    await generate_intentions_from_desires(stub_agent)

    assert stub_agent.active_intention is None
    assert desire.status is DesireStatus.PENDING
