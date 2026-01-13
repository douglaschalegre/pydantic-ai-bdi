"""Plan monitoring and reconsideration for the BDI agent.

This module provides functions for reconsidering the validity of current plans
based on updated beliefs and step execution history.
"""

import traceback
from typing import TYPE_CHECKING
from datetime import datetime
from helper.util import bcolors
from bdi.schemas import ReconsiderResult, DesireStatus

if TYPE_CHECKING:
    from bdi.agent import BDI
    from bdi.schemas import Intention


def generate_history_context(
    intention: "Intention", max_history: int = 3, include_details: bool = False
) -> str:
    """Generate a formatted context string from the intention's step history.

    Args:
        intention: The Intention object containing the step history
        max_history: Maximum number of recent steps to include (default: 3)
        include_details: Whether to include detailed information about each step (default: False)

    Returns:
        A formatted string containing the step history context
    """
    if not intention.step_history:
        return "No previous steps executed."

    recent_history = intention.step_history[-max_history:]

    history_lines = []
    for h in recent_history:
        step_info = f"Step {h.step_number}: {h.step_description} - {'Success' if h.success else 'Failed'}"

        if include_details:
            details = [
                f"  Result: {h.result}",
                f"  Timestamp: {datetime.fromtimestamp(h.timestamp).isoformat()}",
                "  Beliefs Updated:",
            ]

            for belief_name, belief_data in h.beliefs_updated.items():
                details.append(
                    f"    - {belief_name}: {belief_data['value']} (Certainty: {belief_data['certainty']:.2f})"
                )

            step_info += "\n" + "\n".join(details)

        history_lines.append(step_info)

    return "\n".join(history_lines)


async def reconsider_current_intention(agent: "BDI") -> None:
    """Evaluate if the current intention's remaining plan is still valid.

    Based on the current beliefs and step history, determines if the plan
    should continue or if the intention should be removed for replanning.

    Args:
        agent: The BDI agent instance
    """
    if not agent.intentions:
        if agent.verbose:
            print(f"{bcolors.SYSTEM}No intentions to re-consider.{bcolors.ENDC}")
        return

    intention = agent.intentions[0]

    if intention.current_step >= len(intention.steps):
        return

    print(
        f"{bcolors.SYSTEM}  Reconsidering intention for desire '{intention.desire_id}'...{bcolors.ENDC}"
    )

    beliefs_text = (
        "\n".join(
            [
                f"  - {name}: {b.value} (Certainty: {b.certainty:.2f})"
                for name, b in agent.beliefs.beliefs.items()
            ]
        )
        if agent.beliefs.beliefs
        else "  No current beliefs."
    )

    remaining_steps_list = intention.steps[intention.current_step :]
    remaining_steps_text = "\n".join(
        [f"  - {s.description}" for s in remaining_steps_list]
    )

    # Get detailed history context for reconsideration
    history_context = generate_history_context(
        intention,
        max_history=5,  # Show more history for reconsideration
        include_details=True,  # Include detailed information
    )

    reconsider_prompt = f"""
    Current Agent Beliefs:
    {beliefs_text}

    Step History:
    {history_context}

    Remaining Plan Steps (for Desire ID '{intention.desire_id}'):
    {remaining_steps_text}

    Evaluate whether the remaining plan should continue or needs revision.

    Provide your assessment as:
    - valid: true if the plan seems sound to continue, false if it needs revision
    - reason: if valid is false, provide a brief explanation of why the plan is flawed

    Consider:
    1. Is this remaining plan still likely to succeed in achieving the original desire '{intention.desire_id}'?
    2. Are there patterns in the step history suggesting the plan needs adjustment?
    3. Are there contradictions between beliefs, history, and the plan's assumptions?
    4. Based on the history of successful and failed steps, should the plan be modified?
    """

    try:
        if agent.verbose:
            print(
                f"{bcolors.SYSTEM}  Asking LLM to assess plan validity...{bcolors.ENDC}"
            )
        reconsider_result = await agent.run(
            reconsider_prompt, output_type=ReconsiderResult
        )

        if (
            reconsider_result
            and reconsider_result.output
            and reconsider_result.output.valid
        ):
            if agent.verbose:
                print(
                    f"{bcolors.SYSTEM}  LLM Assessment: Plan remains VALID. Reason: {reconsider_result.output.reason}{bcolors.ENDC}"
                )
        else:
            reason = (
                reconsider_result.output.reason
                if (
                    reconsider_result
                    and reconsider_result.output
                    and reconsider_result.output.reason
                )
                else "LLM assessment indicated invalidity or failed."
            )
            print(
                f"{bcolors.WARNING}  LLM Assessment: Plan INVALID. Reason: {reason}{bcolors.ENDC}"
            )
            print(
                f"{bcolors.INTENTION}  Removing invalid intention for desire '{intention.desire_id}'.{bcolors.ENDC}"
            )
            invalid_intention = agent.intentions.popleft()

            for desire in agent.desires:
                if desire.id == invalid_intention.desire_id:
                    print(
                        f"{bcolors.DESIRE}  Setting desire '{desire.id}' back to PENDING.{bcolors.ENDC}"
                    )
                    # Import log_states from logging module
                    from bdi.logging import log_states

                    desire.update_status(DesireStatus.PENDING, lambda **kwargs: log_states(agent, **kwargs))
                    break
            log_states(agent, ["intentions", "desires"])

    except Exception as recon_e:
        print(
            f"{bcolors.FAIL}  Error during intention reconsideration LLM call: {recon_e}{bcolors.ENDC}"
        )
        if agent.verbose:
            traceback.print_exc()

        # Fallback: assume plan is valid but log the error
        print(
            f"{bcolors.WARNING}  Fallback: Assuming plan is valid. Error in reconsideration will not block progress.{bcolors.ENDC}"
        )

        # Log error to markdown file
        if agent.log_file_path:
            from bdi.logging import write_to_log_file

            error_md = f"\n⚠️ **Reconsideration Error:**\n"
            error_md += f"*Failed to evaluate plan validity. Assuming valid and continuing.*\n"
            error_md += f"*Error: {str(recon_e)}*\n"
            write_to_log_file(agent, error_md)

        # Return without invalidating the plan (same as if valid=True)
        return


__all__ = [
    "generate_history_context",
    "reconsider_current_intention",
]
