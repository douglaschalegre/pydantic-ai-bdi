"""Shared desire lifecycle transitions for intentions and desires."""

from collections import deque
from typing import TYPE_CHECKING, Literal

from helper.util import bcolors
from bdi.logging import format_beliefs_for_context, log_states
from bdi.prompts import build_desire_satisfaction_prompt
from bdi.schemas import DesireSatisfactionResult, DesireStatus, PlanStatus

if TYPE_CHECKING:
    from bdi.agent import BDI
    from bdi.schemas import Desire, Intention


RemovalResult = Literal["current", "queued", "missing"]
TERMINAL_DESIRE_STATUSES = {DesireStatus.ACHIEVED, DesireStatus.FAILED}


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


def all_desires_terminal(agent: "BDI") -> bool:
    """Return True when all known desires are terminal."""
    return bool(agent.desires) and all(
        desire.status in TERMINAL_DESIRE_STATUSES for desire in agent.desires
    )


def _find_desire(agent: "BDI", desire_id: str) -> "Desire | None":
    for desire in agent.desires:
        if desire.id == desire_id:
            return desire
    return None


def _remaining_intentions_for_desire(
    agent: "BDI",
    desire_id: str,
    *,
    excluding: "Intention | None" = None,
) -> list["Intention"]:
    return [
        intention
        for intention in agent.intentions
        if intention.desire_id == desire_id and intention is not excluding
    ]


def _remove_intentions_for_desire(agent: "BDI", desire_id: str) -> int:
    original_count = len(agent.intentions)
    agent.intentions = deque(
        intention
        for intention in agent.intentions
        if intention.desire_id != desire_id
    )
    return original_count - len(agent.intentions)


def _format_intention_history(intention: "Intention") -> str:
    plan = intention.active_plan
    if not plan.step_history:
        return "No step history was recorded for this completed Intention."

    lines: list[str] = []
    for history in plan.step_history:
        status = "succeeded" if history.success else "failed"
        lines.append(
            f"- Plan Step {history.step_number + 1}: {history.step_description} ({status})"
        )
        lines.append(f"  Result: {history.result}")
    return "\n".join(lines)


def _format_remaining_intentions(intentions: list["Intention"]) -> str:
    if not intentions:
        return "No remaining Intentions for this Desire."

    lines: list[str] = []
    for index, intention in enumerate(intentions, start=1):
        plan = intention.active_plan
        lines.append(
            f"{index}. {intention.description or '(no description)'}"
        )
        remaining_steps = plan.steps[plan.current_step_index :]
        if not remaining_steps:
            lines.append("   - No remaining steps.")
            continue
        for step_index, step in enumerate(remaining_steps, start=1):
            lines.append(f"   - Plan Step {step_index}: {step.description}")
    return "\n".join(lines)


async def assess_desire_satisfaction(
    agent: "BDI",
    intention: "Intention",
) -> DesireSatisfactionResult:
    """Run the narrow semantic check for whether a desire is satisfied."""
    desire = _find_desire(agent, intention.desire_id)
    remaining_intentions = _remaining_intentions_for_desire(
        agent,
        intention.desire_id,
        excluding=intention,
    )
    prompt = build_desire_satisfaction_prompt(
        intention.desire_id,
        desire.description if desire else "Unknown desire.",
        intention.description or "(no description)",
        _format_intention_history(intention),
        format_beliefs_for_context(agent),
        _format_remaining_intentions(remaining_intentions),
    )

    try:
        assessment_result = await agent.run(
            prompt,
            output_type=DesireSatisfactionResult,
        )
    except Exception as error:
        reason = f"Desire satisfaction assessment failed: {error}"
        print(f"{bcolors.WARNING}  {reason}{bcolors.ENDC}")
        return DesireSatisfactionResult(satisfied=False, reason=reason)

    if not assessment_result or not assessment_result.output:
        return DesireSatisfactionResult(
            satisfied=False,
            reason="Desire satisfaction assessment returned no result.",
        )

    return assessment_result.output


async def complete_intention_and_update_desire(
    agent: "BDI",
    intention: "Intention",
) -> None:
    """Apply lifecycle rules after a full Intention completes."""
    assessment = await assess_desire_satisfaction(agent, intention)
    reason = assessment.reason or "No reason provided."

    if assessment.satisfied:
        removed_count = _remove_intentions_for_desire(agent, intention.desire_id)
        update_desire_status(agent, intention.desire_id, DesireStatus.ACHIEVED)
        print(
            f"{bcolors.DESIRE}  Desire '{intention.desire_id}' satisfied. "
            f"Removed {removed_count} runnable intention(s). Reason: {reason}{bcolors.ENDC}"
        )
        log_states(agent, ["intentions", "desires"])
        return

    remove_intention(agent, intention)
    remaining_intentions = _remaining_intentions_for_desire(agent, intention.desire_id)
    if remaining_intentions:
        update_desire_status(agent, intention.desire_id, DesireStatus.ACTIVE)
        print(
            f"{bcolors.DESIRE}  Desire '{intention.desire_id}' is not satisfied; "
            f"continuing {len(remaining_intentions)} remaining intention(s). Reason: {reason}{bcolors.ENDC}"
        )
    else:
        update_desire_status(agent, intention.desire_id, DesireStatus.PENDING)
        print(
            f"{bcolors.DESIRE}  Desire '{intention.desire_id}' is not satisfied and its plan is exhausted; "
            f"returning to PENDING for replanning. Reason: {reason}{bcolors.ENDC}"
        )

    log_states(agent, ["intentions", "desires"])


def replan_desire_for_intention(
    agent: "BDI",
    intention: "Intention",
    *,
    reason: str,
) -> None:
    """Clear runnable work for an intention's Desire and return it to planning."""
    intention.active_plan.status = PlanStatus.FAILED
    removed_count = _remove_intentions_for_desire(agent, intention.desire_id)
    update_desire_status(agent, intention.desire_id, DesireStatus.PENDING)
    print(
        f"{bcolors.DESIRE}  Desire '{intention.desire_id}' returned to PENDING for replanning. "
        f"Removed {removed_count} runnable intention(s). Reason: {reason}{bcolors.ENDC}"
    )
    log_states(agent, ["intentions", "desires"])


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
    "all_desires_terminal",
    "assess_desire_satisfaction",
    "complete_intention_and_update_desire",
    "finalize_current_intention",
    "replan_desire_for_intention",
    "remove_intention",
    "update_desire_status",
]
