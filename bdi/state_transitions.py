"""Shared helpers for intention/desire lifecycle transitions."""

from typing import TYPE_CHECKING, Literal

from bdi.logging import log_states
from bdi.schemas import DesireStatus

if TYPE_CHECKING:
    from bdi.agent import BDI
    from bdi.schemas import Intention


RemovalResult = Literal["current", "queued", "missing"]


def update_desire_status(
    agent: "BDI",
    desire_id: str,
    status: DesireStatus,
    *,
    force: bool = False,
) -> bool:
    """Update a desire status by ID; returns True when the desire is found."""
    for desire in agent.desires:
        if desire.id != desire_id:
            continue

        if force or desire.status != status:
            desire.update_status(status, lambda **kwargs: log_states(agent, **kwargs))
        return True

    return False


def remove_intention(agent: "BDI", intention: "Intention") -> RemovalResult:
    """Remove an intention from the queue and report where it was removed from."""
    if agent.intentions and agent.intentions[0] == intention:
        agent.intentions.popleft()
        return "current"

    try:
        agent.intentions.remove(intention)
        return "queued"
    except ValueError:
        return "missing"


def finalize_current_intention(
    agent: "BDI",
    intention: "Intention",
    *,
    desire_status: DesireStatus,
    force_status_update: bool = False,
) -> None:
    """Apply final desire state, remove current intention, and log resulting state."""
    update_desire_status(
        agent,
        intention.desire_id,
        desire_status,
        force=force_status_update,
    )
    if agent.intentions and agent.intentions[0] == intention:
        agent.intentions.popleft()
    log_states(agent, ["intentions", "desires"])


__all__ = [
    "RemovalResult",
    "finalize_current_intention",
    "remove_intention",
    "update_desire_status",
]
