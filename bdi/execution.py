"""Intention execution and belief extraction for the BDI agent.

This module handles executing individual steps of intentions, analyzing outcomes,
and extracting beliefs from execution results.
"""

from typing import TYPE_CHECKING, Optional, Dict
from datetime import datetime
import traceback
import json

from helper.util import bcolors
from bdi.schemas import IntentionStep, BeliefExtractionResult, DesireStatus
from bdi.logging import log_states, write_to_log_file, format_beliefs_for_context
from bdi.monitoring import generate_history_context

if TYPE_CHECKING:
    from pydantic_ai.agent import AgentRunResult
    from bdi.agent import BDI


async def analyze_step_outcome_and_update_beliefs(
    agent: "BDI", step: IntentionStep, result: Optional["AgentRunResult"]
) -> bool:
    """Analyze the outcome of an executed step, updates beliefs, and determines success.

    Args:
        agent: The BDI agent instance
        step: The IntentionStep that was executed
        result: The result returned by the base Agent's run method

    Returns:
        True if the step is considered successful, False otherwise
    """
    if agent.verbose:
        print(f"{bcolors.SYSTEM}  Analyzing step outcome...{bcolors.ENDC}")
    if not result:
        print(
            f"{bcolors.WARNING}  Analysis: Step failed - No result returned.{bcolors.ENDC}"
        )
        return False

    if agent.verbose:
        print(
            f"{bcolors.SYSTEM}  (Belief update check based on result: {result.output}){bcolors.ENDC}"
        )

    # Get history context
    intention = agent.intentions[0]
    history_context = generate_history_context(intention)

    # --- Success Assessment (using LLM) ---
    assessment_prompt = f"""
    Original objective for the step: "{step.description}"
    Result obtained: "{result.output}"

    Recent step history:
    {history_context}

    Based on the result obtained and recent history, did the step successfully achieve its original objective?
    Consider the context of previous steps and their outcomes in your assessment.
    Respond with a boolean value: True for success, False for failure.
    """
    step_success = False
    try:
        assessment_result = await agent.run(assessment_prompt, output_type=bool)
        if assessment_result and assessment_result.output:
            if agent.verbose:
                print(
                    f"{bcolors.SYSTEM}  LLM Assessment: Step SUCCEEDED.{bcolors.ENDC}"
                )
            step_success = True
        else:
            failure_reason = (
                assessment_result.output
                if (assessment_result and assessment_result.output)
                else "No assessment result or negative assessment"
            )
            print(
                f"{bcolors.WARNING}  LLM Assessment: Step FAILED. Reason: {failure_reason}{bcolors.ENDC}"
            )
            step_success = False
    except Exception as assess_e:
        print(
            f"{bcolors.FAIL}  Error during LLM success assessment: {assess_e}{bcolors.ENDC}"
        )
        step_success = False

    # --- Belief Extraction ---
    # Extract beliefs from the step result regardless of success/failure
    if agent.verbose:
        print(f"{bcolors.SYSTEM}  Extracting beliefs from step result...{bcolors.ENDC}")

    belief_extraction_prompt = f"""
    Analyze the following step execution and extract any factual information that should be recorded as beliefs.

    Step Objective: "{step.description}"
    Step Result: "{result.output}"
    Step Success: {step_success}

    Extract beliefs about:
    - Factual information discovered (e.g., file paths, status values, API responses)
    - Error causes or constraints (e.g., "path does not exist", "network unavailable")
    - State changes or conditions revealed (e.g., "repository is empty", "file contains X")
    - Tool availability or limitations learned (e.g., "tool requires parameter Y")

    For FAILED steps, focus on extracting information about WHY it failed - these constraints are valuable.
    For SUCCESSFUL steps, extract the positive information discovered.

    Return a list of beliefs with concise names and clear values. Set certainty based on how definitive the information is.
    If no meaningful beliefs can be extracted, return an empty list with an explanation.
    """

    try:
        extraction_result = await agent.run(
            belief_extraction_prompt, output_type=BeliefExtractionResult
        )

        if (
            extraction_result
            and extraction_result.output
            and extraction_result.output.beliefs
        ):
            extracted_beliefs = extraction_result.output.beliefs
            print(
                f"{bcolors.BELIEF}  Extracted {len(extracted_beliefs)} belief(s) from step result.{bcolors.ENDC}"
            )

            # Update the belief set
            for belief in extracted_beliefs:
                agent.beliefs.update(
                    name=belief.name,
                    value=belief.value,
                    source=f"step_{intention.current_step + 1}_{step.description[:30]}",
                    certainty=belief.certainty,
                )
                if agent.verbose:
                    print(
                        f"{bcolors.BELIEF}    + {belief.name}: {belief.value} (Certainty: {belief.certainty:.2f}){bcolors.ENDC}"
                    )

            # Log to markdown file
            if agent.log_file_path:
                beliefs_md = f"🔍 **Beliefs Extracted:**\n"
                beliefs_md += f"*{extraction_result.output.explanation}*\n\n"
                for belief in extracted_beliefs:
                    beliefs_md += f"- **{belief.name}**: {belief.value} (Certainty: {belief.certainty:.2f})\n"
                write_to_log_file(agent, beliefs_md)

        else:
            if agent.verbose:
                explanation = (
                    extraction_result.output.explanation
                    if extraction_result and extraction_result.output
                    else "No explanation provided"
                )
                print(
                    f"{bcolors.SYSTEM}  No beliefs extracted. {explanation}{bcolors.ENDC}"
                )

    except Exception as extract_e:
        print(
            f"{bcolors.FAIL}  Error during belief extraction: {extract_e}{bcolors.ENDC}"
        )
        if agent.verbose:
            traceback.print_exc()

    return step_success


async def execute_intentions(agent: "BDI") -> Dict:
    """Execute one step of the current intention, analyze outcome, and handle success/failure.

    Does NOT proceed to the next step if the current step fails analysis.

    Args:
        agent: The BDI agent instance

    Returns:
        Dictionary with keys:
        - 'hitl_modified_plan': bool - whether HITL modified the plan this execution
        - 'hitl_updated_beliefs': bool - whether HITL updated beliefs
    """
    if not agent.intentions:
        print(f"{bcolors.SYSTEM}No intentions to execute.{bcolors.ENDC}")
        return {"hitl_modified_plan": False, "hitl_updated_beliefs": False}

    intention = agent.intentions[0]

    if intention.current_step >= len(intention.steps):
        print(
            f"{bcolors.INTENTION}Intention for desire '{intention.desire_id}' already completed (found in execute_intentions).{bcolors.ENDC}"
        )
        if intention in agent.intentions:
            for desire in agent.desires:
                if desire.id == intention.desire_id:
                    if desire.status != DesireStatus.ACHIEVED:
                        desire.update_status(
                            DesireStatus.ACHIEVED,
                            lambda **kwargs: log_states(agent, **kwargs),
                        )
                    break
            agent.intentions.popleft()
            log_states(agent, ["intentions", "desires"])
        return {"hitl_modified_plan": False, "hitl_updated_beliefs": False}

    current_step = intention.steps[intention.current_step]
    print(
        f"{bcolors.INTENTION}Executing step {intention.current_step + 1}/{len(intention.steps)} for desire '{intention.desire_id}': {current_step.description}{bcolors.ENDC}"
    )

    # Log step execution start
    if agent.log_file_path:
        step_md = f"#### Step {intention.current_step + 1}/{len(intention.steps)}\n"
        step_md += f"**Desire:** {intention.desire_id}\n"
        step_md += f"**Description:** {current_step.description}\n"
        if current_step.is_tool_call:
            step_md += f"**Tool:** {current_step.tool_name}\n"
            step_md += f"**Parameters:** {json.dumps(current_step.tool_params)}\n"
        step_md += f"*Started: {datetime.now().isoformat()}*"
        write_to_log_file(agent, step_md)

    step_result: Optional["AgentRunResult"] = None
    step_succeeded: bool = False

    try:
        # Get current beliefs to provide context for execution
        beliefs_context = format_beliefs_for_context(agent)

        if current_step.is_tool_call and current_step.tool_name:
            if agent.verbose:
                print(
                    f"{bcolors.SYSTEM}  Attempting tool call via self.run: {current_step.tool_name}({current_step.tool_params}){bcolors.ENDC}"
                )

            # Enhanced tool call prompt with belief context
            tool_prompt = f"""
Current known information (beliefs):
{beliefs_context}

Execute the tool '{current_step.tool_name}' with the suggested parameters: {current_step.tool_params or {}}

You may adjust parameters if current beliefs suggest better values or if conditions have changed.
Perform this action now.
"""
            step_result = await agent.run(tool_prompt)
            print(
                f"{bcolors.SYSTEM}  Tool '{current_step.tool_name}' result: {step_result.output}{bcolors.ENDC}"
            )
        else:
            if agent.verbose:
                print(
                    f"{bcolors.SYSTEM}  Executing descriptive step via self.run: {current_step.description}{bcolors.ENDC}"
                )

            # Enhanced descriptive step prompt with belief context
            enhanced_prompt = f"""
Current known information (beliefs):
{beliefs_context}

Task: {current_step.description}

Consider the current beliefs when executing this task.
"""
            step_result = await agent.run(enhanced_prompt)
            if agent.verbose:
                print(
                    f"{bcolors.SYSTEM}  Step result: {step_result.output}{bcolors.ENDC}"
                )

        step_succeeded = await analyze_step_outcome_and_update_beliefs(
            agent, current_step, step_result
        )

        beliefs_updated = {
            name: {"value": b.value, "source": b.source, "certainty": b.certainty}
            for name, b in agent.beliefs.beliefs.items()
        }
        intention.add_to_history(
            step=current_step,
            result=step_result.output if step_result else "No result",
            success=step_succeeded,
            beliefs_updated=beliefs_updated,
        )

        if step_succeeded:
            print(
                f"{bcolors.INTENTION}  Step {intention.current_step + 1} successful.{bcolors.ENDC}"
            )

            # Log step success
            if agent.log_file_path:
                result_md = f"**Result:** ✅ Success\n"
                result_md += (
                    f"**Output:** {step_result.output if step_result else 'N/A'}\n"
                )
                result_md += f"*Completed: {datetime.now().isoformat()}*"
                write_to_log_file(agent, result_md)

            intention.increment_current_step(
                lambda **kwargs: log_states(agent, **kwargs)
            )

            if intention.current_step >= len(intention.steps):
                print(
                    f"{bcolors.INTENTION}Completed final step. Intention for desire '{intention.desire_id}' finished.{bcolors.ENDC}"
                )
                for desire in agent.desires:
                    if desire.id == intention.desire_id:
                        desire.update_status(
                            DesireStatus.ACHIEVED,
                            lambda **kwargs: log_states(agent, **kwargs),
                        )
                        break
                if agent.intentions and agent.intentions[0] == intention:
                    agent.intentions.popleft()
                log_states(agent, ["intentions", "desires"])
        else:
            print(
                f"{bcolors.WARNING}  Step {intention.current_step + 1} failed analysis. Intention progress paused. Reconsideration pending.{bcolors.ENDC}"
            )

            # Log step failure
            if agent.log_file_path:
                result_md = f"**Result:** ❌ Failed\n"
                result_md += (
                    f"**Output:** {step_result.output if step_result else 'N/A'}\n"
                )
                result_md += f"*Completed: {datetime.now().isoformat()}*"
                write_to_log_file(agent, result_md)

            hitl_success = False
            hitl_updated_beliefs = False
            if agent.enable_human_in_the_loop:
                try:
                    # Import here to avoid circular dependency
                    from bdi.hitl import human_in_the_loop_intervention

                    (
                        hitl_success,
                        hitl_updated_beliefs,
                    ) = await human_in_the_loop_intervention(
                        agent, intention, current_step, step_result
                    )
                except Exception as hitl_e:
                    print(
                        f"{bcolors.FAIL}Error during HITL intervention: {hitl_e}{bcolors.ENDC}"
                    )
                    if agent.verbose:
                        traceback.print_exc()

            if hitl_success:
                print(
                    f"{bcolors.SYSTEM}  HITL intervention successful. Step will be retried in next cycle.{bcolors.ENDC}"
                )
                # Return HITL info to skip reconsideration in bdi_cycle
                return {
                    "hitl_modified_plan": True,
                    "hitl_updated_beliefs": hitl_updated_beliefs,
                }
            else:
                log_states(agent, ["beliefs"])

    except Exception as e:
        print(
            f"{bcolors.FAIL}------------------------------------------------------------{bcolors.ENDC}"
        )
        print(
            f"{bcolors.FAIL}Exception during execution/analysis of step for intention '{intention.desire_id}':{bcolors.ENDC}"
        )
        traceback.print_exc()
        print(f"{bcolors.FAIL}Error Message: {e}{bcolors.ENDC}")
        print(
            f"{bcolors.FAIL}------------------------------------------------------------{bcolors.ENDC}"
        )

        # Log exception
        if agent.log_file_path:
            error_md = f"**Result:** 🔥 Exception\n"
            error_md += f"**Error:** {str(e)}\n"
            error_md += f"**Traceback:**\n```\n{traceback.format_exc()}\n```\n"
            error_md += f"*Timestamp: {datetime.now().isoformat()}*"
            write_to_log_file(agent, error_md)

        beliefs_updated = {
            name: {"value": b.value, "source": b.source, "certainty": b.certainty}
            for name, b in agent.beliefs.beliefs.items()
        }
        intention.add_to_history(
            step=current_step,
            result=f"Exception: {str(e)}",
            success=False,
            beliefs_updated=beliefs_updated,
        )

        for desire in agent.desires:
            if desire.id == intention.desire_id:
                desire.update_status(
                    DesireStatus.FAILED, lambda **kwargs: log_states(agent, **kwargs)
                )
                break
        if agent.intentions and agent.intentions[0] == intention:
            agent.intentions.popleft()
        log_states(agent, ["intentions", "desires"])

    # Normal completion (no HITL intervention)
    return {"hitl_modified_plan": False, "hitl_updated_beliefs": False}


__all__ = [
    "analyze_step_outcome_and_update_beliefs",
    "execute_intentions",
]
