import pytest

import bdi.cycle as cycle
from bdi.schemas import DesireStatus


@pytest.mark.asyncio
async def test_cycle_does_not_plan_pending_desires_while_intention_active(
    monkeypatch,
    stub_agent,
) -> None:
    active_desire = stub_agent.add_desire(
        desire_id="desire_active",
        description="Active work",
        status=DesireStatus.ACTIVE,
    )
    pending_desire = stub_agent.add_desire(
        desire_id="desire_pending",
        description="Pending work",
        status=DesireStatus.PENDING,
    )
    active_intention = stub_agent.set_current_intention(
        desire_id=active_desire.id,
        step_descriptions=["continue active work"],
    )

    async def fail_if_planning_runs(_agent):
        raise AssertionError("planning should not run while an intention is active")

    async def execute_without_finishing(_agent):
        return {"hitl_modified_plan": False, "hitl_updated_beliefs": False}

    async def skip_reconsideration(_agent):
        return None

    monkeypatch.setattr(cycle, "generate_intentions_from_desires", fail_if_planning_runs)
    monkeypatch.setattr(cycle, "execute_intentions", execute_without_finishing)
    monkeypatch.setattr(cycle, "reconsider_current_intention", skip_reconsideration)

    result = await cycle.bdi_cycle(stub_agent)

    assert result == "executed"
    assert list(stub_agent.intentions) == [active_intention]
    assert active_desire.status is DesireStatus.ACTIVE
    assert pending_desire.status is DesireStatus.PENDING
    assert stub_agent.run_calls == []
