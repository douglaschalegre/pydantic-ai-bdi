from collections import deque

from bdi.schemas import DesireStatus, Intention, IntentionStep
from bdi.state_transitions import (
    finalize_current_intention,
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


def test_remove_intention_reports_origin(stub_agent) -> None:
    current = Intention(
        desire_id="desire_current",
        steps=[IntentionStep(description="current step")],
    )
    queued = Intention(
        desire_id="desire_queued",
        steps=[IntentionStep(description="queued step")],
    )
    missing = Intention(
        desire_id="desire_missing",
        steps=[IntentionStep(description="missing step")],
    )
    stub_agent.intentions = deque([current, queued])

    assert remove_intention(stub_agent, queued) == "queued"
    assert remove_intention(stub_agent, current) == "current"
    assert remove_intention(stub_agent, missing) == "missing"


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
