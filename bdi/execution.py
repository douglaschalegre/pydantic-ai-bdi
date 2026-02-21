"""Intention execution and belief extraction for the BDI agent.

This module handles executing individual steps of intentions, analyzing outcomes,
and extracting beliefs from execution results.
"""

from typing import TYPE_CHECKING, Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime
import traceback
import json

from helper.util import bcolors
from bdi.schemas import IntentionStep, BeliefExtractionResult, DesireStatus, StepAssessmentResult
from bdi.errors import is_validation_output_error
from bdi.logging import log_states, format_beliefs_for_context
from bdi.monitoring import generate_history_context
from bdi.prompts import (
    build_descriptive_execution_prompt,
    build_step_assessment_prompt,
    build_step_belief_extraction_prompt,
    build_tool_execution_prompt,
)
from bdi.state_transitions import finalize_current_intention

if TYPE_CHECKING:
    from pydantic_ai.agent import AgentRunResult
    from bdi.agent import BDI

# Fixed retry configuration - opinionated approach
MAX_STEP_RETRIES = 2  # Total of 3 attempts per step


@dataclass
class StepRetryContext:
    """Transient context for tracking retry attempts during step execution.

    This is NOT persisted in schemas - it's execution-time only.
    """

    attempt_number: int = 0  # 0 = first attempt, 1+ = retries
    failure_history: List[Dict[str, Any]] = field(default_factory=list)

    def record_failure(
        self, result_output: str, beliefs_extracted: List[Dict[str, Any]]
    ):
        """Record a failed attempt with its beliefs."""
        self.failure_history.append(
            {
                "attempt": self.attempt_number,
                "result": result_output,
                "beliefs": beliefs_extracted,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def should_retry(self) -> bool:
        """Determine if we should retry based on attempt count."""
        return self.attempt_number < MAX_STEP_RETRIES

    def is_retry(self) -> bool:
        """Check if current execution is a retry."""
        return self.attempt_number > 0


async def extract_relevant_beliefs_from_result(
    agent: "BDI",
    step: IntentionStep,
    result: Optional["AgentRunResult"],
    step_success: bool,
) -> List[Dict[str, Any]]:
    """Extract beliefs from a step result without updating the belief set.

    This is used during retry attempts to gather failure information.

    Args:
        agent: The BDI agent instance
        step: The IntentionStep that was executed
        result: The result returned by the agent's run method
        step_success: Whether the step was assessed as successful

    Returns:
        List of belief dictionaries with keys: name, value, certainty
    """
    if agent.verbose:
        print(f"{bcolors.SYSTEM}  Extracting beliefs from step result...{bcolors.ENDC}")

    belief_extraction_prompt = build_step_belief_extraction_prompt(
        step.description,
        result.output if result else "No result",
        step_success,
    )

    extracted_beliefs = []

    try:
        extraction_result = await agent.run(
            belief_extraction_prompt, output_type=BeliefExtractionResult
        )

        if (
            extraction_result
            and extraction_result.output
            and extraction_result.output.beliefs
        ):
            for belief in extraction_result.output.beliefs:
                extracted_beliefs.append(
                    {
                        "name": belief.name,
                        "value": belief.value,
                        "certainty": belief.certainty,
                    }
                )

            if agent.verbose:
                print(
                    f"{bcolors.BELIEF}  Extracted {len(extracted_beliefs)} belief(s).{bcolors.ENDC}"
                )

    except Exception as extract_e:
        # Belief extraction is non-critical - log a warning but don't spam with tracebacks
        if is_validation_output_error(extract_e):
            # Common case: LLM returned wrong format - just note it briefly
            if agent.verbose:
                print(
                    f"{bcolors.WARNING}  Belief extraction skipped: LLM output format issue.{bcolors.ENDC}"
                )
        else:
            # Unexpected error - show more detail
            print(
                f"{bcolors.WARNING}  Belief extraction failed: {extract_e}{bcolors.ENDC}"
            )
            if agent.verbose:
                traceback.print_exc()

    return extracted_beliefs


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
    step_type = (
        f"Tool call: {step.tool_name}"
        if step.is_tool_call and step.tool_name
        else "Descriptive step"
    )
    assessment_prompt = build_step_assessment_prompt(
        step.description,
        result.output,
        step_type,
        history_context,
    )

    step_success = False
    try:
        assessment_result = await agent.run(assessment_prompt, output_type=StepAssessmentResult)
        if assessment_result and assessment_result.output and assessment_result.output.success:
            if agent.verbose:
                print(
                    f"{bcolors.SYSTEM}  LLM Assessment: Step SUCCEEDED.{bcolors.ENDC}"
                )
                if assessment_result.output.reason:
                    print(
                        f"{bcolors.SYSTEM}  Reason: {assessment_result.output.reason}{bcolors.ENDC}"
                    )
            step_success = True
        else:
            reason = (
                assessment_result.output.reason
                if (assessment_result and assessment_result.output and assessment_result.output.reason)
                else "No assessment result or negative assessment"
            )
            print(
                f"{bcolors.WARNING}  LLM Assessment: Step FAILED. Reason: {reason}{bcolors.ENDC}"
            )
            step_success = False

    except Exception as assess_e:
        print(
            f"{bcolors.FAIL}  Error during LLM success assessment: {assess_e}{bcolors.ENDC}"
        )

        # INTELLIGENT FALLBACK: Don't default to failure
        # For tool calls, check if the result contains error indicators
        if step.is_tool_call and result and result.output:
            error_indicators = ["error", "exception", "failed to", "could not", "not found", "does not exist"]
            result_lower = result.output.lower()

            has_error = any(indicator in result_lower for indicator in error_indicators)
            has_substantial_output = len(result.output) > 50

            if not has_error and has_substantial_output:
                print(
                    f"{bcolors.SYSTEM}  Fallback: Tool call returned substantial data without errors - marking as SUCCESS.{bcolors.ENDC}"
                )
                step_success = True
            else:
                print(
                    f"{bcolors.WARNING}  Fallback: Tool call appears to have failed - marking as FAILURE.{bcolors.ENDC}"
                )
                step_success = False
        else:
            # For non-tool calls, default to failure since we can't assess
            print(
                f"{bcolors.WARNING}  Fallback: Cannot assess non-tool step - marking as FAILURE.{bcolors.ENDC}"
            )
            step_success = False

    # --- Belief Extraction ---
    # Extract beliefs from the step result regardless of success/failure
    extracted_beliefs = await extract_relevant_beliefs_from_result(
        agent, step, result, step_success
    )

    # Update the belief set with extracted beliefs
    if extracted_beliefs:
        intention = agent.intentions[0]
        print(
            f"{bcolors.BELIEF}  Updating belief set with {len(extracted_beliefs)} belief(s).{bcolors.ENDC}"
        )

        for belief_dict in extracted_beliefs:
            agent.beliefs.update(
                name=belief_dict["name"],
                value=belief_dict["value"],
                source=f"step_{intention.current_step + 1}_{step.description[:30]}",
                certainty=belief_dict["certainty"],
            )
            if agent.verbose:
                print(
                    f"{bcolors.BELIEF}    + {belief_dict['name']}: {belief_dict['value']} (Certainty: {belief_dict['certainty']:.2f}){bcolors.ENDC}"
                )
    else:
        if agent.verbose:
            print(f"{bcolors.SYSTEM}  No beliefs extracted.{bcolors.ENDC}")

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
        finalize_current_intention(
            agent,
            intention,
            desire_status=DesireStatus.ACHIEVED,
        )
        return {"hitl_modified_plan": False, "hitl_updated_beliefs": False}

    current_step = intention.steps[intention.current_step]
    print(
        f"{bcolors.INTENTION}Executing step {intention.current_step + 1}/{len(intention.steps)} for desire '{intention.desire_id}': {current_step.description}{bcolors.ENDC}"
    )

    # Initialize retry context
    retry_ctx = StepRetryContext(attempt_number=0)

    step_result: Optional["AgentRunResult"] = None
    step_succeeded: bool = False

    # RETRY LOOP - Will execute at least once (attempt_number=0)
    while True:
        # Determine if this is a retry attempt
        is_retry = retry_ctx.is_retry()
        attempt_label = (
            f"(Attempt {retry_ctx.attempt_number + 1}/{MAX_STEP_RETRIES + 1})"
        )

        if is_retry:
            print(
                f"{bcolors.WARNING}  Retrying step {intention.current_step + 1} {attempt_label}{bcolors.ENDC}"
            )

        try:
            # Get current beliefs to provide context for execution
            beliefs_context = format_beliefs_for_context(agent)

            # Build retry-aware prompt context
            retry_context = ""
            if is_retry and retry_ctx.failure_history:
                retry_context = "\n\nPREVIOUS ATTEMPT FAILURES:\n"
                for failure in retry_ctx.failure_history:
                    retry_context += (
                        f"- Attempt {failure['attempt'] + 1}: {failure['result']}\n"
                    )
                    if failure["beliefs"]:
                        retry_context += (
                            f"  Beliefs learned: {json.dumps(failure['beliefs'])}\n"
                        )
                retry_context += "\nPlease consider these failures and adjust your approach accordingly.\n"

            if current_step.is_tool_call and current_step.tool_name:
                if agent.verbose:
                    print(
                        f"{bcolors.SYSTEM}  Attempting tool call via self.run: {current_step.tool_name}({current_step.tool_params}){bcolors.ENDC}"
                    )

                # Enhanced tool call prompt with belief context AND retry context
                tool_prompt = build_tool_execution_prompt(
                    beliefs_context,
                    retry_context,
                    current_step.tool_name,
                    current_step.tool_params or {},
                    is_retry,
                )
                step_result = await agent.run(tool_prompt)
                print(
                    f"{bcolors.SYSTEM}  Tool '{current_step.tool_name}' result: {step_result.output}{bcolors.ENDC}"
                )

                # DEBUG: Log all tool calls that occurred
                if agent.verbose and step_result.all_messages():
                    print(
                        f"{bcolors.SYSTEM}  === DEBUG: Tool Call Details ==={bcolors.ENDC}"
                    )
                    for msg in step_result.all_messages():
                        if hasattr(msg, "parts"):
                            for part in msg.parts:
                                if hasattr(part, "tool_name"):
                                    print(
                                        f"{bcolors.SYSTEM}    Tool: {part.tool_name}{bcolors.ENDC}"
                                    )
                                    if hasattr(part, "args"):
                                        print(
                                            f"{bcolors.SYSTEM}    Args: {part.args}{bcolors.ENDC}"
                                        )
                                elif hasattr(part, "tool_call_id"):
                                    print(
                                        f"{bcolors.SYSTEM}    Result: {part.content[:200]}...{bcolors.ENDC}"
                                    )
                    print(
                        f"{bcolors.SYSTEM}  === End Tool Call Details ==={bcolors.ENDC}"
                    )
            else:
                if agent.verbose:
                    print(
                        f"{bcolors.SYSTEM}  Executing descriptive step via self.run: {current_step.description}{bcolors.ENDC}"
                    )

                # Enhanced descriptive step prompt with belief context AND retry context
                enhanced_prompt = build_descriptive_execution_prompt(
                    beliefs_context,
                    retry_context,
                    current_step.description,
                    is_retry,
                )
                step_result = await agent.run(enhanced_prompt)
                if agent.verbose:
                    print(
                        f"{bcolors.SYSTEM}  Step result: {step_result.output}{bcolors.ENDC}"
                    )

            # Analyze outcome
            step_succeeded = await analyze_step_outcome_and_update_beliefs(
                agent, current_step, step_result
            )

            # If step succeeded, break out of retry loop
            if step_succeeded:
                print(
                    f"{bcolors.INTENTION}  Step {intention.current_step + 1} successful{' after retry' if is_retry else ''}.{bcolors.ENDC}"
                )
                break

            # Step failed - extract beliefs from failure for retry context
            extracted_beliefs = await extract_relevant_beliefs_from_result(
                agent, current_step, step_result, step_succeeded
            )

            # Record this failure in retry context
            retry_ctx.record_failure(
                result_output=step_result.output if step_result else "No result",
                beliefs_extracted=extracted_beliefs,
            )

            # Increment attempt counter
            retry_ctx.attempt_number += 1

            # Check if we should retry or escalate to HITL
            if retry_ctx.should_retry():
                print(
                    f"{bcolors.WARNING}  Step {intention.current_step + 1} failed. Auto-retry enabled (attempt {retry_ctx.attempt_number + 1}/{MAX_STEP_RETRIES + 1}).{bcolors.ENDC}"
                )
                # Continue to next iteration of while loop (retry)
                continue
            else:
                # Retry exhausted, break to handle HITL or failure
                print(
                    f"{bcolors.WARNING}  Step {intention.current_step + 1} failed after {retry_ctx.attempt_number} retries. Escalating...{bcolors.ENDC}"
                )
                break

        except Exception as e:
            # Exception during execution - do NOT retry, fail immediately
            print(f"{bcolors.FAIL}Exception during step execution: {e}{bcolors.ENDC}")
            traceback.print_exc()

            # Record in history and fail the intention
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

            finalize_current_intention(
                agent,
                intention,
                desire_status=DesireStatus.FAILED,
                force_status_update=True,
            )

            # Return early - no HITL for exceptions
            return {"hitl_modified_plan": False, "hitl_updated_beliefs": False}

    # END OF RETRY LOOP - Now handle success or failure with HITL

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
        intention.increment_current_step(lambda **kwargs: log_states(agent, **kwargs))

        if intention.current_step >= len(intention.steps):
            print(
                f"{bcolors.INTENTION}Completed final step. Intention for desire '{intention.desire_id}' finished.{bcolors.ENDC}"
            )
            finalize_current_intention(
                agent,
                intention,
                desire_status=DesireStatus.ACHIEVED,
            )
    else:
        # Step failed after all retries - now trigger HITL if enabled
        print(
            f"{bcolors.WARNING}  Step {intention.current_step + 1} failed analysis after {retry_ctx.attempt_number} attempt(s). Intention progress paused.{bcolors.ENDC}"
        )

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

    # Normal completion (no HITL intervention)
    return {"hitl_modified_plan": False, "hitl_updated_beliefs": False}


__all__ = [
    "analyze_step_outcome_and_update_beliefs",
    "execute_intentions",
]
