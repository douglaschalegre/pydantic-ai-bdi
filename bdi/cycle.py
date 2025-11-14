"""BDI reasoning cycle orchestration.

This module implements the main BDI reasoning cycle that coordinates belief updates,
deliberation, intention generation, execution, and plan monitoring.
"""

from typing import TYPE_CHECKING
from datetime import datetime

from helper.util import bcolors
from bdi.schemas import DesireStatus
from bdi.logging import log_states, write_to_log_file
from bdi.planning import generate_intentions_from_desires
from bdi.execution import execute_intentions
from bdi.monitoring import reconsider_current_intention

if TYPE_CHECKING:
    from bdi.agent import BDI


async def bdi_cycle(agent: "BDI") -> None:
    """Run one BDI reasoning cycle including reconsideration.

    The cycle follows the standard BDI architecture phases:
    1. Belief Update (via action outcomes in execution)
    2. Deliberation (desire status check)
    3. Intention Generation (if needed)
    4. Intention Execution (one step)
    5. Reconsideration (plan validity monitoring)

    Args:
        agent: The BDI agent instance
    """
    agent.cycle_count += 1

    # Log cycle start
    if agent.log_file_path:
        write_to_log_file(
            agent,
            f"**Cycle {agent.cycle_count} Start**\n*Timestamp: {datetime.now().isoformat()}*",
            section_title=f"BDI Cycle {agent.cycle_count}",
        )

    log_states(
        agent,
        types=["beliefs", "desires", "intentions"],
        message="States before starting BDI cycle",
    )
    print(f"{bcolors.SYSTEM}\n--- BDI Cycle Start ---{bcolors.ENDC}")

    # 1. Belief Update (Triggered by Action Outcomes)
    # Beliefs are updated within analyze_step_outcome_and_update_beliefs
    # after an action is taken in execute_intentions.
    if agent.verbose:
        print(f"{bcolors.BELIEF}Current Beliefs:{bcolors.ENDC}")
        log_states(agent, ["beliefs"])

    # 2. Deliberation / Desire Status Check
    # Check for active/pending desires.
    if agent.verbose:
        print(f"{bcolors.DESIRE}Current Desires:{bcolors.ENDC}")
        log_states(agent, ["desires"])
    active_desires = [
        d
        for d in agent.desires
        if d.status in [DesireStatus.PENDING, DesireStatus.ACTIVE]
    ]

    # 3. Intention Generation (if needed)
    # If we have active/pending desires but no intentions queued, generate them.
    if active_desires and not agent.intentions:
        print(
            f"{bcolors.SYSTEM}No current intentions, but active/pending desires exist. Generating intentions...{bcolors.ENDC}"
        )
        await generate_intentions_from_desires(agent)
    else:
        if agent.verbose:
            print(f"{bcolors.INTENTION}Current Intentions:{bcolors.ENDC}")
            log_states(agent, ["intentions"])
        if not agent.intentions:
            print(
                f"{bcolors.SYSTEM}No intentions pending and no active desires require new ones.{bcolors.ENDC}"
            )

    # 4. Intention Execution (One Step)
    hitl_info = {"hitl_modified_plan": False, "hitl_updated_beliefs": False}
    if agent.intentions:
        hitl_info = await execute_intentions(agent)
    else:
        print(f"{bcolors.SYSTEM}No intentions to execute this cycle.{bcolors.ENDC}")

    # 5. Reconsideration (Plan Monitoring)
    # After executing a step (successfully or not), reconsider the current plan.
    # SKIP reconsideration if HITL just modified the plan (give it a chance to execute first)
    if hitl_info.get("hitl_modified_plan", False):
        print(
            f"{bcolors.SYSTEM}  Skipping reconsideration: HITL just modified the plan. Will retry modified step in next cycle.{bcolors.ENDC}"
        )
        if hitl_info.get("hitl_updated_beliefs", False):
            print(
                f"{bcolors.BELIEF}  Note: Beliefs were updated from HITL guidance and are now persisted.{bcolors.ENDC}"
            )
    elif agent.intentions:  # Check if an intention still exists
        current_intention = agent.intentions[0]
        # Only reconsider if the intention wasn't just completed/removed by execute_intentions
        if not current_intention.steps or current_intention.current_step < len(
            current_intention.steps
        ):
            await reconsider_current_intention(agent)
        else:
            print(
                f"{bcolors.SYSTEM}  Skipping reconsideration: Current intention just completed, removed, or has no steps.{bcolors.ENDC}"
            )
    else:
        print(
            f"{bcolors.SYSTEM}  Skipping reconsideration: No intentions remaining.{bcolors.ENDC}"
        )

    print(f"{bcolors.SYSTEM}--- BDI Cycle End ---{bcolors.ENDC}")
    log_states(
        agent,
        types=["beliefs", "desires", "intentions"],
        message="States after BDI cycle",
    )

    # Log cycle end
    if agent.log_file_path:
        write_to_log_file(
            agent,
            f"**Cycle {agent.cycle_count} End**\n*Timestamp: {datetime.now().isoformat()}*\n\n---",
        )


__all__ = [
    "bdi_cycle",
]
