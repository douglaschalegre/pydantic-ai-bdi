"""Planning and deliberation for the BDI agent.

This module handles the two-stage LLM-based intention generation process that
converts high-level desires into detailed, actionable plans (intentions with steps).
"""

from typing import TYPE_CHECKING, List
from collections import deque

from helper.util import bcolors
from bdi.schemas import (
    Intention,
    HighLevelIntentionList,
    DetailedStepList,
)
from bdi.logging import log_states

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
        print(
            f"{bcolors.SYSTEM}No desires to generate intentions from.{bcolors.ENDC}"
        )
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
    guidance_section = ""
    if agent.initial_intention_guidance:
        guidance_text = "\n".join(
            [f"- {g}" for g in agent.initial_intention_guidance]
        )
        guidance_section = f"\n\nUser-Provided Strategic Guidance (Consider these as high-level intentions to guide planning):\n{guidance_text}"

    if agent.verbose:
        print(
            f"{bcolors.SYSTEM}Stage 1: Generating high-level intentions...{bcolors.ENDC}"
        )
    prompt_stage1 = f"""
    Given the following overall desires and current beliefs, identify high-level intentions required to fulfill these desires.
    For each relevant desire, propose one or more concise intentions. Each intention should represent a distinct goal or task achievable *by you, the AI agent*.

    Focus ONLY on WHAT needs to be done at a high level, but ensure these goals are achievable through information processing, analysis, or using the available tools.
    Do *not* propose intentions that require physical actions in the real world (e.g., installing hardware), direct interaction with physical systems beyond your tool capabilities, or capabilities you do not possess based on the available tools.

    Overall Desires:
    {desires_text}
    {guidance_section}

    Current Beliefs:
    {beliefs_text}

    Available Tools:
    (The underlying Pydantic AI agent will provide the available tools, including those from MCP, to the LLM.)

    Respond with a list of high-level intentions using the required format. Associate each intention with its corresponding desire ID.
    """
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

        prompt_stage2 = f"""
        Your task is to create a detailed, step-by-step action plan to achieve the following high-level intention:
        '{hl_intention.description}' (This contributes to overall Desire ID: {hl_intention.desire_id})

        Consider the current beliefs and available tools to formulate the plan.
        Each step in the plan must be a single, concrete action that *you, the AI agent*, can perform. Steps MUST be one of the following:
        1. A specific call to an available tool (listed below), including necessary parameters based on context and beliefs.
        2. An internal information processing or analysis task (e.g., 'Analyze sensor data', 'Summarize report X', 'Compare belief A and B', 'Decide next action based on criteria Y').

        Do *not* generate steps requiring physical actions, interaction with the physical world outside of tool capabilities, or capabilities you do not possess.

        Current Beliefs:
        {beliefs_text}

        IMPORTANT: When planning steps, actively use current beliefs:
        - Skip discovery steps if beliefs already contain the needed information
        - Use belief values to set initial tool parameters (e.g., if belief contains a path, use it)
        - Account for constraints or limitations revealed in beliefs (e.g., if a belief indicates something failed, don't retry the same way)
        - Build upon information already known rather than re-discovering it

        Available Tools:
        (The underlying Pydantic AI agent will provide the available tools, including those from MCP, to the LLM.)

        STEP DESCRIPTION GUIDELINES:
        - Write step descriptions as ACTIONS to perform, not questions to answer (e.g., "Retrieve git commit history" NOT "Check if repository path exists")
        - For tool calls, describe WHAT the tool will do (e.g., "Use git_log to fetch commit history with max_count=50")
        - For analysis tasks, describe the OUTPUT expected (e.g., "Extract commit summary from git log results and create presentation outline")
        - Avoid CHECK/VERIFY steps unless they're truly validation steps with binary success criteria

        Generate a sequence of detailed steps required to execute this intention. Ensure the steps are logical and sequential.
        Structure the output as a list of steps according to the required format.
        Focus exclusively on HOW to achieve the intention '{hl_intention.description}' using only the allowed action types.
        Provide parameters for tool calls based on the context and beliefs.
        """
        try:
            stage2_result = await agent.run(
                prompt_stage2, output_type=DetailedStepList
            )
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
