"""Plan monitoring and reconsideration for the BDI agent.

This module provides functions for reconsidering the validity of current plans
based on updated beliefs and step execution history.
"""

import traceback
from typing import TYPE_CHECKING
from datetime import datetime
from voluntas._utils import bcolors
from voluntas.schemas import Plan, PlanStatus, PlanStep, ReconsiderResult
from voluntas.prompts import build_reconsideration_prompt
from voluntas.logging import log_states
from voluntas.state_transitions import fail_desire_for_intention, replan_desire_for_intention

if TYPE_CHECKING:
    from voluntas.agent import BDI
    from voluntas.schemas import Intention


def generate_history_context(
    intention: "Intention", max_history: int = 3, include_details: bool = False
) -> str:
    """Generate a formatted context string from the active Plan's step history.

    Args:
        intention: The Intention object owning the Plan Step History
        max_history: Maximum number of recent steps to include (default: 3)
        include_details: Whether to include detailed information about each step (default: False)

    Returns:
        A formatted string containing the step history context
    """
    plan = intention.active_plan
    if not plan.step_history:
        return "No previous steps executed."

    recent_history = plan.step_history[-max_history:]

    history_lines = []
    for h in recent_history:
        step_info = f"Plan Step {h.step_number + 1}: {h.step_description} - {'Success' if h.success else 'Failed'}"

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


def _format_steps(steps) -> str:
    if not steps:
        return "  No Plan Steps."
    return "\n".join([f"  - {step.description}" for step in steps])


def _format_completed_steps(intention: "Intention") -> str:
    completed = [h for h in intention.active_plan.step_history if h.success]
    if not completed:
        return "  No completed Plan Steps."

    return "\n".join(
        [
            f"  - Plan Step {h.step_number + 1}: {h.step_description} -> {h.result}"
            for h in completed
        ]
    )


def _format_failure_history(intention: "Intention") -> str:
    failures = [h for h in intention.active_plan.step_history if not h.success]
    if not failures:
        return "  No relevant failures recorded."

    return "\n".join(
        [
            f"  - Plan Step {h.step_number + 1}: {h.step_description} -> {h.result}"
            for h in failures
        ]
    )


def _apply_plan_repair(
    agent: "BDI",
    intention: "Intention",
    repaired_steps: list[PlanStep],
    *,
    reason: str,
) -> None:
    """Replace remaining Plan Steps while preserving Intention and history."""
    plan = intention.active_plan
    plan.steps = plan.steps[: plan.current_step_index] + repaired_steps
    plan.status = PlanStatus.ACTIVE
    print(
        f"{bcolors.INTENTION}  Repaired Plan for desire '{intention.desire_id}' while preserving the active Intention. Reason: {reason}{bcolors.ENDC}"
    )
    log_states(agent, ["intentions", "desires"])


def _apply_plan_replacement(
    agent: "BDI",
    intention: "Intention",
    replacement_steps: list[PlanStep],
    *,
    reason: str,
) -> None:
    """Replace the active Plan while preserving Intention and prior history."""
    previous_history = intention.active_plan.step_history
    intention.active_plan = Plan(
        steps=replacement_steps,
        status=PlanStatus.ACTIVE,
        step_history=previous_history,
    )
    print(
        f"{bcolors.INTENTION}  Replaced Plan for desire '{intention.desire_id}' while preserving the active Intention. Reason: {reason}{bcolors.ENDC}"
    )
    log_states(agent, ["intentions", "desires"])


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
    plan = intention.active_plan

    if plan.is_complete():
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

    remaining_steps_text = _format_steps(plan.steps[plan.current_step_index :])
    completed_steps_text = _format_completed_steps(intention)
    failure_history_text = _format_failure_history(intention)

    reconsider_prompt = build_reconsideration_prompt(
        beliefs_text,
        completed_steps_text,
        intention.desire_id,
        remaining_steps_text,
        failure_history_text,
    )

    try:
        if agent.verbose:
            print(
                f"{bcolors.SYSTEM}  Asking LLM to assess plan validity...{bcolors.ENDC}"
            )
        reconsider_result = await agent.run(
            reconsider_prompt, output_type=ReconsiderResult
        )

        if not reconsider_result or not reconsider_result.output:
            action = "continue"
            reason = "Reconsideration returned no structured result."
        else:
            action = reconsider_result.output.action
            reason = reconsider_result.output.reason or "No reason provided."

        if action == "continue":
            plan.status = PlanStatus.ACTIVE
            if agent.verbose:
                print(
                    f"{bcolors.SYSTEM}  LLM Assessment: Continue Plan. Reason: {reason}{bcolors.ENDC}"
                )
        elif action == "repair_plan":
            print(
                f"{bcolors.WARNING}  LLM Assessment: {action}. Reason: {reason}{bcolors.ENDC}"
            )
            if reconsider_result and reconsider_result.output and reconsider_result.output.plan_steps:
                _apply_plan_repair(
                    agent,
                    intention,
                    reconsider_result.output.plan_steps,
                    reason=reason,
                )
            else:
                print(
                    f"{bcolors.WARNING}  repair_plan returned no Plan Steps; returning Desire to planning.{bcolors.ENDC}"
                )
                replan_desire_for_intention(agent, intention, reason=reason)
        elif action == "replace_plan":
            print(
                f"{bcolors.WARNING}  LLM Assessment: {action}. Reason: {reason}{bcolors.ENDC}"
            )
            if reconsider_result and reconsider_result.output and reconsider_result.output.plan_steps:
                _apply_plan_replacement(
                    agent,
                    intention,
                    reconsider_result.output.plan_steps,
                    reason=reason,
                )
            else:
                print(
                    f"{bcolors.WARNING}  replace_plan returned no Plan Steps; returning Desire to planning.{bcolors.ENDC}"
                )
                replan_desire_for_intention(agent, intention, reason=reason)
        elif action == "fail_desire":
            print(
                f"{bcolors.WARNING}  LLM Assessment: fail_desire. Reason: {reason}{bcolors.ENDC}"
            )
            fail_desire_for_intention(agent, intention, reason=reason)
        else:
            print(
                f"{bcolors.WARNING}  Unknown reconsideration action '{action}'. Replanning conservatively. Reason: {reason}{bcolors.ENDC}"
            )
            replan_desire_for_intention(agent, intention, reason=reason)

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

        # Return without invalidating the plan (same as if valid=True)
        return


__all__ = [
    "generate_history_context",
    "reconsider_current_intention",
]
