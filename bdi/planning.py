"""Planning and deliberation for the BDI agent.

This module handles the two-stage LLM-based intention generation process that
converts high-level desires into detailed, actionable plans (intentions with steps).
"""

from typing import TYPE_CHECKING, List
from collections import deque

from helper.util import bcolors
from bdi.schemas import (
    Intention,
    HighLevelIntention,
    HighLevelIntentionList,
    DetailedStepList,
    DesireStatus,
)
from bdi.logging import log_states
from bdi.prompts import build_planning_stage1_prompt, build_planning_stage2_prompt

if TYPE_CHECKING:
    from bdi.agent import BDI


async def generate_intentions_from_desires(agent: "BDI") -> None:
    """Convert desires into detailed, actionable intentions using a two-stage LLM process.

    Stage 1: Generate high-level intentions (WHAT to achieve)
    Stage 2: For each high-level intention, generate detailed steps (HOW to achieve it)

    Args:
        agent: The BDI agent instance
    """
    if not agent.desires:
        print(f"{bcolors.SYSTEM}No desires to generate intentions from.{bcolors.ENDC}")
        return
    if agent.intentions:
        print(
            f"{bcolors.SYSTEM}Intentions already exist, skipping generation.{bcolors.ENDC}"
        )
        return

    if agent.verbose:
        print(
            f"{bcolors.SYSTEM}Starting two-stage intention generation...{bcolors.ENDC}"
        )
    final_intentions: List[Intention] = []

    # --- Context Gathering (Common for both stages) ---
    desires_text = "\n".join(
        [f"- ID: {d.id}, Description: {d.description}" for d in agent.desires]
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

    # --- Stage 1: Generate High-Level Intentions ---
    # Check if explicit intentions were provided by the user
    # If so, use them directly instead of generating via LLM
    high_level_intentions: List[HighLevelIntention] = []

    if agent.initial_intention_guidance:
        # User provided explicit intentions - use them directly
        # Associate all intentions with the first active/pending desire
        # (In most cases, explicit intentions relate to a single primary desire)
        active_desires = [
            d
            for d in agent.desires
            if d.status in [DesireStatus.PENDING, DesireStatus.ACTIVE]
        ]
        primary_desire_id = (
            active_desires[0].id if active_desires else agent.desires[0].id
        )

        print(
            f"{bcolors.SYSTEM}Using {len(agent.initial_intention_guidance)} explicit intentions provided by user (skipping Stage 1 LLM).{bcolors.ENDC}"
        )

        for intention_desc in agent.initial_intention_guidance:
            high_level_intentions.append(
                HighLevelIntention(
                    desire_id=primary_desire_id,
                    description=intention_desc,
                )
            )
            if agent.verbose:
                print(f"{bcolors.INTENTION}  - {intention_desc}{bcolors.ENDC}")
    else:
        # No explicit intentions - generate via LLM (original Stage 1 behavior)
        if agent.verbose:
            print(
                f"{bcolors.SYSTEM}Stage 1: Generating high-level intentions...{bcolors.ENDC}"
            )
        prompt_stage1 = build_planning_stage1_prompt(desires_text, beliefs_text)
        try:
            stage1_result = await agent.run(
                prompt_stage1, output_type=HighLevelIntentionList
            )
            if (
                not stage1_result
                or not stage1_result.output
                or not stage1_result.output.intentions
            ):
                print(
                    f"{bcolors.FAIL}Stage 1 failed: No high-level intentions generated.{bcolors.ENDC}"
                )
                return
            high_level_intentions = stage1_result.output.intentions
            print(
                f"{bcolors.SYSTEM}Stage 1 successful: Generated {len(high_level_intentions)} high-level intentions.{bcolors.ENDC}"
            )

        except Exception as e:
            print(
                f"{bcolors.FAIL}Stage 1 failed: Error during LLM call: {e}{bcolors.ENDC}"
            )
            return

    if not high_level_intentions:
        print(
            f"{bcolors.FAIL}No high-level intentions available for Stage 2.{bcolors.ENDC}"
        )
        return

    # --- Stage 2: Generate Detailed Steps for Each High-Level Intention ---
    if agent.verbose:
        print(
            f"{bcolors.SYSTEM}Stage 2: Generating detailed steps for each intention...{bcolors.ENDC}"
        )
    for hl_intention in high_level_intentions:
        if agent.verbose:
            print(
                f"{bcolors.INTENTION}  Processing high-level intention for Desire '{hl_intention.desire_id}': {hl_intention.description}{bcolors.ENDC}"
            )

        prompt_stage2 = build_planning_stage2_prompt(
            hl_intention.description,
            hl_intention.desire_id,
            beliefs_text,
        )
        try:
            stage2_result = await agent.run(prompt_stage2, output_type=DetailedStepList)
            if (
                not stage2_result
                or not stage2_result.output
                or not stage2_result.output.steps
            ):
                print(
                    f"{bcolors.WARNING}  Stage 2 warning: No detailed steps generated for intention '{hl_intention.description}'. Skipping.{bcolors.ENDC}"
                )
                continue

            detailed_steps = stage2_result.output.steps
            if agent.verbose:
                print(
                    f"{bcolors.SYSTEM}    Generated {len(detailed_steps)} detailed steps.{bcolors.ENDC}"
                )

            final_intention = Intention(
                desire_id=hl_intention.desire_id,
                description=hl_intention.description,
                steps=detailed_steps,
            )
            final_intentions.append(final_intention)

        except Exception as e:
            print(
                f"{bcolors.FAIL}  Stage 2 failed for intention '{hl_intention.description}': Error during LLM call: {e}{bcolors.ENDC}"
            )

    # --- Update Agent State ---
    agent.intentions = deque(final_intentions)
    print(
        f"{bcolors.SYSTEM}Intention generation complete. Updated agent with {len(agent.intentions)} detailed intentions.{bcolors.ENDC}"
    )
    log_states(agent, ["intentions"])


__all__ = [
    "generate_intentions_from_desires",
]
