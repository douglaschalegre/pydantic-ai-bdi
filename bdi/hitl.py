"""Human-in-the-loop (HITL) intervention system for the BDI agent.

This module provides the complete HITL interaction flow, allowing human users
to intervene when the agent encounters failures, providing guidance that gets
interpreted via LLM and applied to modify the agent's plan.
"""

from typing import TYPE_CHECKING, Dict, Any, Optional, Tuple
from datetime import datetime
import traceback
import json

from helper.util import bcolors
from bdi.schemas import (
    IntentionStep,
    PlanManipulationDirective,
    DesireStatus,
)
from bdi.logging import log_states, write_to_log_file

if TYPE_CHECKING:
    from pydantic_ai.agent import AgentRunResult
    from bdi.agent import BDI
    from bdi.schemas import Intention


def build_failure_context(
    agent: "BDI",
    intention: "Intention",
    failed_step: IntentionStep,
    step_result: Optional["AgentRunResult"],
) -> Dict[str, Any]:
    """Gather all relevant information about a step failure into a structured dictionary.

    Args:
        agent: The BDI agent instance
        intention: The current intention being executed
        failed_step: The step that failed
        step_result: The result from the failed step execution

    Returns:
        Dictionary containing comprehensive failure context
    """
    context = {
        "desire_id": intention.desire_id,
        "failed_step_description": failed_step.description,
        "failed_step_number": intention.current_step + 1,
        "total_steps_in_plan": len(intention.steps),
        "is_tool_call": failed_step.is_tool_call,
        "tool_name": failed_step.tool_name if failed_step.is_tool_call else None,
        "tool_params": failed_step.tool_params
        if failed_step.is_tool_call
        else None,
        "step_result_output": step_result.output
        if step_result and hasattr(step_result, "output")
        else "No result data",
        "llm_step_assessment": "Step was deemed a FAILURE by internal analysis.",
        "current_beliefs": {
            name: {
                "value": b.value,
                "source": b.source,
                "certainty": b.certainty,
                "timestamp": datetime.fromtimestamp(b.timestamp).isoformat(),
            }
            for name, b in agent.beliefs.beliefs.items()
        }
        if agent.beliefs.beliefs
        else "No current beliefs.",
        "remaining_plan_steps": [
            {
                "description": s.description,
                "is_tool_call": s.is_tool_call,
                "tool_name": s.tool_name,
                "tool_params": s.tool_params,
            }
            for s in intention.steps[intention.current_step + 1 :]
        ],
        "original_failed_step_object": failed_step.model_dump(),
    }
    return context


def present_context_to_user(failure_context: Dict[str, Any]) -> None:
    """Present the failure context to the user in a readable format.

    Args:
        failure_context: Dictionary containing failure information
    """
    print(
        f"{bcolors.FAIL}------------------------------------------------------------{bcolors.ENDC}"
    )
    print(
        f"{bcolors.FAIL}HUMAN INTERVENTION REQUIRED for Desire '{failure_context['desire_id']}'{bcolors.ENDC}"
    )
    print(
        f"{bcolors.FAIL}------------------------------------------------------------{bcolors.ENDC}"
    )
    print(
        f"Failed Step ({failure_context['failed_step_number']}/{failure_context['total_steps_in_plan']}): {failure_context['failed_step_description']}"
    )
    if failure_context["is_tool_call"]:
        print(
            f"  Tool Call: {failure_context['tool_name']}({json.dumps(failure_context['tool_params']) if failure_context['tool_params'] else '{}'})"
        )

    print(f"Step Result Data: {failure_context['step_result_output']}")

    print(f"Agent Assessment: {failure_context['llm_step_assessment']}")

    print("\nCurrent Beliefs:")
    if isinstance(failure_context["current_beliefs"], dict):
        if failure_context["current_beliefs"]:
            for name, b_details in failure_context["current_beliefs"].items():
                print(
                    f"  - {name}: {b_details['value']} (Source: {b_details['source']}, Certainty: {b_details['certainty']:.2f}, Time: {b_details['timestamp']})"
                )
        else:
            print("  (None)")
    else:
        print(f"  {failure_context['current_beliefs']}")

    if failure_context["remaining_plan_steps"]:
        print("\nRemaining Plan Steps:")
        for i, step_data in enumerate(failure_context["remaining_plan_steps"]):
            print(f"  {i + 1}. {step_data['description']}")
    else:
        print("\nNo remaining steps in this plan.")
    print(
        f"{bcolors.FAIL}------------------------------------------------------------{bcolors.ENDC}"
    )


async def interpret_user_nl_guidance(
    agent: "BDI", user_nl_instruction: str, failure_context: Dict[str, Any]
) -> Optional[PlanManipulationDirective]:
    """Interpret the user's natural language guidance using an LLM call.

    Args:
        agent: The BDI agent instance
        user_nl_instruction: User's natural language instruction
        failure_context: Context about the failure

    Returns:
        A structured PlanManipulationDirective or None if interpretation fails
    """
    if agent.verbose:
        print(
            f"{bcolors.SYSTEM}  Interpreting user NL guidance via LLM...{bcolors.ENDC}"
        )

    # Get available tool descriptions if possible
    tools_description_for_llm = "Available tools will be provided by the system. Focus on their general capabilities if specific schemas aren't listed here."
    if hasattr(agent, "tool_configs") and agent.tool_configs:
        tools_list = []
        for tool_name, tool_config in agent.tool_configs.items():
            schema_info = "Schema: (provided by system)"
            if hasattr(tool_config, "model_json_schema"):
                schema_info = f"Input schema: {json.dumps(tool_config.model_json_schema().get('properties', {}))}"
            elif callable(tool_config):
                docstring = getattr(tool_config, "__doc__", "No description.")
                schema_info = (
                    f"Description: {docstring.strip() if docstring else 'N/A'}"
                )
            tools_list.append(f"- {tool_name}: {schema_info}")
        if tools_list:
            tools_description_for_llm = (
                "Available Tools (use these for new steps if applicable):\\n"
                + "\\n".join(tools_list)
            )

    prompt = f"""
    The BDI agent encountered a failure during plan execution.
    The user has provided natural language guidance on how to proceed.
    Your task is to interpret this guidance and translate it into a structured PlanManipulationDirective.

    Current Failure Context:
    - Desire ID: {failure_context["desire_id"]}
    - Failed Step ({failure_context["failed_step_number"]}/{failure_context["total_steps_in_plan"]}): "{failure_context["failed_step_description"]}"
    - Original Failed Step Object: {json.dumps(failure_context["original_failed_step_object"])}
    - Is Tool Call: {failure_context["is_tool_call"]}
    - Tool Name: {failure_context["tool_name"] if failure_context["is_tool_call"] else "N/A"}
    - Tool Params Used: {json.dumps(failure_context["tool_params"]) if failure_context["is_tool_call"] and failure_context["tool_params"] else "N/A"}
    - Step Result Data: {json.dumps(failure_context["step_result_output"])}
    - Current Beliefs: {json.dumps(failure_context["current_beliefs"])}
    - Remaining Plan Steps (after failed one): {json.dumps(failure_context["remaining_plan_steps"])}

    User's Natural Language Guidance:
    "{user_nl_instruction}"

    {tools_description_for_llm}

    Instructions for you, the LLM:
    1. Analyze the user's guidance in the context of the failure.
    2. Determine the most appropriate 'manipulation_type' from the available literals in PlanManipulationDirective.

    CRITICAL: Extract Factual Information to Beliefs
    3. **ALWAYS populate 'beliefs_to_update' when the user provides factual information**, REGARDLESS of manipulation_type.
       This is INDEPENDENT of plan modification. You can extract beliefs AND modify the plan in the same directive.
       Examples of factual information to extract as beliefs:
       * File paths (e.g., "the repo is at /path/to/repo" → belief: repo_path = "/path/to/repo")
       * Status values (e.g., "the service is offline" → belief: service_status = "offline")
       * Configuration values (e.g., "use port 8080" → belief: server_port = "8080")
       * Constraints (e.g., "that API requires authentication" → belief: api_requires_auth = "true")
       * Error causes (e.g., "path doesn't exist" → belief: path_invalid = "true")

    Plan Manipulation:
    4. If the user suggests modifying the current step, populate 'current_step_modifications' with a dictionary of changes. For tool calls, this is often a new 'tool_params' dictionary. For descriptive steps, it might be a new 'description'.
    5. If the user suggests new steps, populate 'new_steps_definition' with a list of dictionaries. Each dictionary must conform to the IntentionStep schema (fields: description, is_tool_call, tool_name, tool_params).
       If generating tool calls, ensure 'tool_name' is valid from the available tools and 'tool_params' are appropriate.

    Summary:
    6. Provide a concise 'user_guidance_summary' explaining your interpretation, chosen action, AND any beliefs extracted.
    7. If the user's guidance is unclear, a comment, or cannot be mapped to a specific plan manipulation, use 'COMMENT_NO_ACTION' and explain in the summary (but still extract beliefs if factual information was provided).

    REMEMBER: Belief extraction and plan manipulation are ORTHOGONAL. Even when choosing MODIFY_CURRENT_AND_RETRY or RETRY_CURRENT_AS_IS, if the user provides factual information, EXTRACT IT TO BELIEFS.
    """

    try:
        if agent.verbose:
            print(
                f"{bcolors.SYSTEM}  Sending user guidance to LLM for interpretation...{bcolors.ENDC}"
            )

        llm_response = await agent.run(prompt, output_type=PlanManipulationDirective)

        if llm_response and llm_response.output:
            if agent.verbose:
                print(
                    f"{bcolors.SYSTEM}  LLM interpretation successful. Directive: {llm_response.output.model_dump_json(indent=2)}{bcolors.ENDC}"
                )
            return llm_response.output
        else:
            error_msg = (
                "LLM did not return valid data for PlanManipulationDirective."
            )
            print(f"{bcolors.FAIL}  {error_msg}{bcolors.ENDC}")
            return None
    except Exception as e:
        print(
            f"{bcolors.FAIL}  Exception during LLM call for NL guidance interpretation: {e}{bcolors.ENDC}"
        )
        traceback.print_exc()
        return None


def summarize_directive_for_user(
    directive: PlanManipulationDirective,
) -> str:
    """Translate a PlanManipulationDirective into a human-readable summary.

    Args:
        directive: The plan manipulation directive to summarize

    Returns:
        Human-readable summary string
    """
    summary_parts = [
        f"Action Type: {directive.manipulation_type.replace('_', ' ').title()}"
    ]
    summary_parts.append(f"LLM's Understanding: {directive.user_guidance_summary}")

    if (
        directive.manipulation_type == "MODIFY_CURRENT_AND_RETRY"
        and directive.current_step_modifications
    ):
        summary_parts.append(
            f"  - Modifications to current step: {json.dumps(directive.current_step_modifications)}"
        )

    if directive.new_steps_definition:
        if directive.manipulation_type in [
            "REPLACE_CURRENT_STEP_WITH_NEW",
            "INSERT_NEW_STEPS_BEFORE_CURRENT",
            "INSERT_NEW_STEPS_AFTER_CURRENT",
            "REPLACE_REMAINDER_OF_PLAN",
        ]:
            summary_parts.append("  - New Steps Proposed:")
            for i, step_def in enumerate(directive.new_steps_definition):
                desc = step_def.get("description", "N/A")
                tool_name = step_def.get("tool_name")
                tool_params = step_def.get("tool_params")
                step_summary = f"    {i + 1}. Description: '{desc}'"
                if tool_name:
                    step_summary += f" (Tool: {tool_name}, Params: {json.dumps(tool_params) if tool_params else '{}'})"
                summary_parts.append(step_summary)

    if (
        directive.manipulation_type == "UPDATE_BELIEFS_AND_RETRY"
        and directive.beliefs_to_update
    ):
        summary_parts.append("  - Belief Updates Proposed:")
        for name, belief_data in directive.beliefs_to_update.items():
            summary_parts.append(
                f"    - '{name}': {belief_data.get('value', 'N/A')}"
            )

    return "\\n".join(summary_parts)


async def handle_user_abort_request(agent: "BDI", intention: "Intention") -> None:
    """Manage aborting an intention based on user request.

    Args:
        agent: The BDI agent instance
        intention: The intention to abort
    """
    print(
        f"{bcolors.INTENTION}  User requested ABORT of intention for desire '{intention.desire_id}'.{bcolors.ENDC}"
    )
    original_desire_id = intention.desire_id

    if agent.intentions and agent.intentions[0] == intention:
        agent.intentions.popleft()
        log_states(
            agent,
            ["intentions"],
            message=f"Intention for desire '{original_desire_id}' removed due to user abort.",
        )
    else:
        try:
            agent.intentions.remove(intention)
            log_states(
                agent,
                ["intentions"],
                message=f"Intention for desire '{original_desire_id}' (not current) removed due to user abort.",
            )
        except ValueError:
            print(
                f"{bcolors.WARNING}  Warning: Intention for desire '{original_desire_id}' not found in queue during abort.{bcolors.ENDC}"
            )

    for desire_obj in agent.desires:
        if desire_obj.id == original_desire_id:
            desire_obj.update_status(DesireStatus.PENDING, lambda **kwargs: log_states(agent, **kwargs))
            print(
                f"{bcolors.DESIRE}  Desire '{original_desire_id}' status set to PENDING for potential replanning.{bcolors.ENDC}"
            )
            break


async def apply_user_guided_action(
    agent: "BDI",
    directive: PlanManipulationDirective,
    intention: "Intention",
) -> Tuple[bool, bool]:
    """Apply the plan manipulation based on the LLM-interpreted and user-confirmed guidance.

    Args:
        agent: The BDI agent instance
        directive: The plan manipulation directive to apply
        intention: The current intention being modified

    Returns:
        Tuple of (applied_successfully, beliefs_updated)
    """

    idx = intention.current_step
    applied_successfully = False
    beliefs_updated = False

    manip_type = directive.manipulation_type
    print(
        f"{bcolors.SYSTEM}  Applying user guidance: {manip_type} - {directive.user_guidance_summary}{bcolors.ENDC}"
    )

    # FIRST: Extract and apply beliefs if user provided factual information
    # This happens BEFORE and INDEPENDENT of plan manipulation
    if directive.beliefs_to_update:
        print(
            f"{bcolors.BELIEF}  Extracting beliefs from HITL guidance...{bcolors.ENDC}"
        )
        for name, belief_data_dict in directive.beliefs_to_update.items():
            belief_data_dict.setdefault("name", name)
            belief_data_dict.setdefault("source", "human_guidance")
            belief_data_dict.setdefault("certainty", 1.0)
            belief_data_dict.setdefault("timestamp", datetime.now().timestamp())
            try:
                agent.beliefs.update(
                    name=name,
                    value=belief_data_dict["value"],
                    source=belief_data_dict["source"],
                    certainty=belief_data_dict["certainty"],
                )
                if agent.verbose:
                    print(
                        f"{bcolors.BELIEF}    + {name}: {belief_data_dict['value']} (Source: human_guidance){bcolors.ENDC}"
                    )
                beliefs_updated = True
            except KeyError as e:
                print(
                    f"{bcolors.FAIL}  Failed to update belief '{name}' due to missing data: {e}{bcolors.ENDC}"
                )
            except Exception as e:
                print(
                    f"{bcolors.FAIL}  Failed to update belief '{name}': {e}{bcolors.ENDC}"
                )

        if beliefs_updated:
            log_states(
                agent, ["beliefs"], message="Beliefs updated from HITL guidance."
            )

    # THEN: Apply plan manipulation
    try:
        if manip_type == "RETRY_CURRENT_AS_IS":
            applied_successfully = True

        elif manip_type == "MODIFY_CURRENT_AND_RETRY":
            if directive.current_step_modifications and idx < len(intention.steps):
                step_to_modify = intention.steps[idx]
                for (
                    field_name,
                    new_value,
                ) in directive.current_step_modifications.items():
                    if hasattr(step_to_modify, field_name):
                        setattr(step_to_modify, field_name, new_value)
                    else:
                        print(
                            f"{bcolors.WARNING}  Cannot modify unknown field '{field_name}' in step.{bcolors.ENDC}"
                        )
                log_states(
                    agent,
                    ["intentions"],
                    message=f"Intention step {idx} modified by user guidance.",
                )
                applied_successfully = True
            else:
                print(
                    f"{bcolors.WARNING}  No modifications provided or invalid step index for MODIFY_CURRENT_AND_RETRY. Retrying as is.{bcolors.ENDC}"
                )
                applied_successfully = True

        elif manip_type in [
            "REPLACE_CURRENT_STEP_WITH_NEW",
            "INSERT_NEW_STEPS_BEFORE_CURRENT",
            "INSERT_NEW_STEPS_AFTER_CURRENT",
            "REPLACE_REMAINDER_OF_PLAN",
        ]:
            if directive.new_steps_definition:
                new_steps_list = [
                    IntentionStep(**step_def)
                    for step_def in directive.new_steps_definition
                ]

                if manip_type == "REPLACE_CURRENT_STEP_WITH_NEW":
                    if idx < len(intention.steps):
                        intention.steps.pop(idx)
                        for i, new_step in enumerate(new_steps_list):
                            intention.steps.insert(idx + i, new_step)
                    else:
                        raise IndexError(
                            "Invalid step index for REPLACE_CURRENT_STEP_WITH_NEW"
                        )
                elif manip_type == "INSERT_NEW_STEPS_BEFORE_CURRENT":
                    for i, new_step in enumerate(new_steps_list):
                        intention.steps.insert(idx + i, new_step)
                elif manip_type == "INSERT_NEW_STEPS_AFTER_CURRENT":
                    insert_point = idx + 1
                    for i, new_step in enumerate(new_steps_list):
                        intention.steps.insert(insert_point + i, new_step)
                elif manip_type == "REPLACE_REMAINDER_OF_PLAN":
                    intention.steps = intention.steps[:idx]
                    intention.steps.extend(new_steps_list)
                    if not intention.steps:
                        print(
                            f"{bcolors.WARNING}  Plan became empty after REPLACE_REMAINDER. Aborting intention.{bcolors.ENDC}"
                        )
                        await handle_user_abort_request(agent, intention)
                        return (True, beliefs_updated)

                log_states(
                    agent,
                    ["intentions"],
                    message=f"Intention modified by user guidance ({manip_type}).",
                )
                applied_successfully = True
            else:
                print(
                    f"{bcolors.WARNING}  No new steps provided for {manip_type}. Reconsidering.{bcolors.ENDC}"
                )
                applied_successfully = False

        elif manip_type == "SKIP_CURRENT_STEP":
            if idx < len(intention.steps):
                intention.increment_current_step(lambda **kwargs: log_states(agent, **kwargs))
                if intention.current_step >= len(intention.steps):
                    print(
                        f"{bcolors.INTENTION}  Skipping step completed intention for desire '{intention.desire_id}'.{bcolors.ENDC}"
                    )
                    for desire_obj in agent.desires:
                        if desire_obj.id == intention.desire_id:
                            desire_obj.update_status(
                                DesireStatus.ACHIEVED, lambda **kwargs: log_states(agent, **kwargs)
                            )
                            break
                    if agent.intentions and agent.intentions[0] == intention:
                        agent.intentions.popleft()
                    log_states(agent, ["intentions", "desires"])
                applied_successfully = True
            else:
                print(
                    f"{bcolors.WARNING}  Cannot skip, already at end of plan or invalid index.{bcolors.ENDC}"
                )
                applied_successfully = False

        elif manip_type == "ABORT_INTENTION":
            await handle_user_abort_request(agent, intention)
            applied_successfully = True

        elif manip_type == "UPDATE_BELIEFS_AND_RETRY":
            # Beliefs already updated above, just retry the step
            if not directive.beliefs_to_update:
                print(
                    f"{bcolors.WARNING}  User Guidance: Update beliefs, but no beliefs provided. Retrying as is.{bcolors.ENDC}"
                )
            applied_successfully = True

        elif manip_type == "COMMENT_NO_ACTION":
            print(
                f"{bcolors.SYSTEM}  User comment received, no direct action on plan. Reconsidering.{bcolors.ENDC}"
            )
            applied_successfully = False

        else:
            print(
                f"{bcolors.WARNING}  Unknown or unhandled manipulation_type: {manip_type}. Reconsidering.{bcolors.ENDC}"
            )
            applied_successfully = False

    except IndexError as e:
        print(
            f"{bcolors.FAIL}  Error applying plan manipulation due to invalid step index: {e}{bcolors.ENDC}"
        )
        traceback.print_exc()
        applied_successfully = False
    except Exception as e:
        print(
            f"{bcolors.FAIL}  Error applying plan manipulation directive '{manip_type}': {e}{bcolors.ENDC}"
        )
        traceback.print_exc()
        applied_successfully = False

    return (applied_successfully, beliefs_updated)


async def human_in_the_loop_intervention(
    agent: "BDI",
    intention: "Intention",
    failed_step: IntentionStep,
    step_result: Optional["AgentRunResult"],
) -> Tuple[bool, bool]:
    """Orchestrate the full human-in-the-loop interaction when a step fails.

    Args:
        agent: The BDI agent instance
        intention: The current intention being executed
        failed_step: The step that failed
        step_result: The result from the failed step

    Returns:
        Tuple of (applied_successfully, beliefs_updated)
    """
    if agent.verbose:
        print(
            f"{bcolors.SYSTEM}Starting human-in-the-loop intervention...{bcolors.ENDC}"
        )

    # Log HITL start
    if agent.log_file_path:
        hitl_md = f"### Human-in-the-Loop Intervention\n"
        hitl_md += f"**Desire:** {intention.desire_id}\n"
        hitl_md += f"**Failed Step:** {failed_step.description}\n"
        hitl_md += f"*Started: {datetime.now().isoformat()}*"
        write_to_log_file(agent, hitl_md)

    # 1. Build failure context
    failure_context = build_failure_context(
        agent, intention, failed_step, step_result
    )

    # 2. Present context to user
    present_context_to_user(failure_context)

    # 3. Get user guidance
    print(
        f"\n{bcolors.SYSTEM}Please provide guidance on how to proceed (or 'quit' to exit HITL):{bcolors.ENDC}"
    )
    try:
        user_input = input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        print(
            f"\n{bcolors.WARNING}HITL interaction interrupted. Continuing without user guidance.{bcolors.ENDC}"
        )
        return (False, False)

    if user_input.lower() in ["quit", "exit", "q"]:
        print(
            f"{bcolors.SYSTEM}User chose to exit HITL. Continuing without guidance.{bcolors.ENDC}"
        )
        return (False, False)

    if not user_input:
        print(
            f"{bcolors.WARNING}No guidance provided. Continuing without changes.{bcolors.ENDC}"
        )
        return (False, False)

    # 4. Interpret user guidance via LLM
    directive = await interpret_user_nl_guidance(agent, user_input, failure_context)

    if not directive:
        print(
            f"{bcolors.FAIL}Failed to interpret user guidance. Continuing without changes.{bcolors.ENDC}"
        )
        return (False, False)

    # 5. Present interpretation back to user for confirmation
    summary = summarize_directive_for_user(directive)
    print(f"\n{bcolors.SYSTEM}LLM Interpretation of your guidance:{bcolors.ENDC}")
    print(summary)

    print(f"\n{bcolors.SYSTEM}Apply this guidance? (y/n/edit):{bcolors.ENDC}")
    try:
        confirmation = input("> ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print(
            f"\n{bcolors.WARNING}Confirmation interrupted. Not applying guidance.{bcolors.ENDC}"
        )
        return (False, False)

    if confirmation in ["n", "no"]:
        print(
            f"{bcolors.SYSTEM}User declined to apply guidance. Trying again...{bcolors.ENDC}"
        )
        return await human_in_the_loop_intervention(
            agent, intention, failed_step, step_result
        )
    elif confirmation in ["edit", "e"]:
        print(f"{bcolors.SYSTEM}Please provide revised guidance:{bcolors.ENDC}")
        try:
            revised_input = input("> ").strip()
            if revised_input:
                revised_directive = await interpret_user_nl_guidance(
                    agent, revised_input, failure_context
                )
                if revised_directive:
                    directive = revised_directive
                else:
                    print(
                        f"{bcolors.FAIL}Failed to interpret revised guidance. Using original.{bcolors.ENDC}"
                    )
            else:
                print(
                    f"{bcolors.WARNING}No revised guidance provided. Using original.{bcolors.ENDC}"
                )
        except (EOFError, KeyboardInterrupt):
            print(
                f"\n{bcolors.WARNING}Edit interrupted. Using original guidance.{bcolors.ENDC}"
            )
    elif confirmation not in ["y", "yes"]:
        print(f"{bcolors.WARNING}Invalid response. Assuming 'yes'.{bcolors.ENDC}")

    # 6. Apply the guidance
    applied_successfully, beliefs_updated = await apply_user_guided_action(
        agent, directive, intention
    )

    # Log HITL outcome
    if agent.log_file_path:
        outcome_md = f"**User Input:** {user_input}\n"
        outcome_md += f"**Action Type:** {directive.manipulation_type}\n"
        outcome_md += f"**LLM Interpretation:** {directive.user_guidance_summary}\n"
        outcome_md += f"**Applied Successfully:** {'✅ Yes' if applied_successfully else '❌ No'}\n"
        if beliefs_updated:
            outcome_md += f"**Beliefs Updated:** ✅ Yes\n"
        outcome_md += f"*Completed: {datetime.now().isoformat()}*"
        write_to_log_file(agent, outcome_md)

    if applied_successfully:
        print(f"{bcolors.SYSTEM}User guidance applied successfully.{bcolors.ENDC}")
        return (True, beliefs_updated)
    else:
        print(
            f"{bcolors.WARNING}Failed to apply user guidance completely.{bcolors.ENDC}"
        )
        return (False, beliefs_updated)


__all__ = [
    "build_failure_context",
    "present_context_to_user",
    "interpret_user_nl_guidance",
    "summarize_directive_for_user",
    "handle_user_abort_request",
    "apply_user_guided_action",
    "human_in_the_loop_intervention",
]
