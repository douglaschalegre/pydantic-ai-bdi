"""Planning and deliberation for the BDI agent.

This module selects one pending Desire and adopts one high-level Intention. The
Intention is executed as one descriptive step, letting the execution agent use
tools and reconcile outcomes without pre-expanding a brittle detailed plan.
"""

from typing import TYPE_CHECKING

from voluntas._utils import bcolors
from voluntas.schemas import (
    Intention,
    PlanningDecision,
    DesireStatus,
    Plan,
    PlanStep,
)
from voluntas.logging import log_states
from voluntas.prompts import build_planning_stage1_prompt
from voluntas.state_transitions import update_desire_status

if TYPE_CHECKING:
    from voluntas.agent import BDI


def _build_intention(decision: PlanningDecision) -> Intention:
    """Represent a high-level intention as one executable descriptive step."""
    return Intention(
        desire_id=decision.desire_id,
        description=decision.description,
        active_plan=Plan(
            steps=[PlanStep(description=decision.description)],
        ),
    )


async def generate_intentions_from_desires(agent: "BDI") -> None:
    """Convert desires into high-level executable intentions.

    The planner performs one planning pass and commits one pending Desire as one
    Intention with one Plan.

    Args:
        agent: The BDI agent instance
    """
    if not agent.desires:
        print(f"{bcolors.SYSTEM}No desires to generate intentions from.{bcolors.ENDC}")
        return
    if agent.active_intention is not None:
        print(
            f"{bcolors.SYSTEM}Intentions already exist, skipping generation.{bcolors.ENDC}"
        )
        return

    pending_desires = [d for d in agent.desires if d.status is DesireStatus.PENDING]
    if not pending_desires:
        print(f"{bcolors.SYSTEM}No pending desires to plan for.{bcolors.ENDC}")
        return

    if agent.verbose:
        print(
            f"{bcolors.SYSTEM}Starting single-stage intention generation...{bcolors.ENDC}"
        )

    # --- Context Gathering ---
    desires_text = "\n".join(
        [f"- ID: {d.id}, Description: {d.description}" for d in pending_desires]
    )
    beliefs_text = (
        "\n".join(
            [
                f"- {name}: {belief.value} (Source: {belief.source}, Certainty: {belief.certainty:.2f})"
                for name, belief in agent.beliefs.beliefs.items()
            ]
        )
        if agent.beliefs.beliefs
        else "No current beliefs."
    )

    use_explicit_intentions = bool(agent.initial_intention_guidance) and not getattr(
        agent,
        "_initial_intention_guidance_consumed",
        False,
    )

    if use_explicit_intentions:
        agent._initial_intention_guidance_consumed = True
        print(
            f"{bcolors.SYSTEM}Using first explicit intention provided by user (skipping planning LLM).{bcolors.ENDC}"
        )
        decision = PlanningDecision(
            desire_id=pending_desires[0].id,
            description=agent.initial_intention_guidance[0],
        )
        if agent.verbose:
            print(f"{bcolors.INTENTION}  - {decision.description}{bcolors.ENDC}")
    else:
        # No explicit intentions - generate high-level intentions via LLM.
        if agent.verbose:
            print(
                f"{bcolors.SYSTEM}Generating high-level intentions...{bcolors.ENDC}"
            )
        intention_guidance_text = (
            "\n".join(f"- {item}" for item in agent.initial_intention_guidance)
            if agent.initial_intention_guidance
            else None
        )
        prompt_stage1 = build_planning_stage1_prompt(
            desires_text,
            beliefs_text,
            intention_guidance_text,
        )
        try:
            stage1_result = await agent.run(
                prompt_stage1, output_type=PlanningDecision
            )
            if not stage1_result or not stage1_result.output:
                print(
                    f"{bcolors.FAIL}Intention generation failed: No planning decision generated.{bcolors.ENDC}"
                )
                return
            decision = stage1_result.output

        except Exception as e:
            print(
                f"{bcolors.FAIL}Intention generation failed: Error during LLM call: {e}{bcolors.ENDC}"
            )
            return

    if decision.desire_id not in {desire.id for desire in pending_desires}:
        print(
            f"{bcolors.FAIL}Planning decision targeted a Desire that is not pending.{bcolors.ENDC}"
        )
        return

    final_intention = _build_intention(decision)

    # --- Update Agent State ---
    agent.active_intention = final_intention
    update_desire_status(agent, final_intention.desire_id, DesireStatus.ACTIVE)
    print(
        f"{bcolors.SYSTEM}Intention generation complete. Updated agent with one high-level intention.{bcolors.ENDC}"
    )
    log_states(agent, ["intentions"])


__all__ = [
    "generate_intentions_from_desires",
]
