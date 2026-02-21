"""Prompt builders for BDI modules.

Centralizes long prompt text to keep operational code paths easier to read.
"""

from typing import Any
import json
from textwrap import dedent


def build_initial_belief_extraction_prompt(desires_text: str) -> str:
    return dedent(
        f"""
        Analyze the following desire descriptions and extract any factual information that should be recorded as beliefs.

        Desire Descriptions:
        {desires_text}

        Extract ONLY concrete, factual information explicitly stated in the desires, such as:
        - File paths or directory paths (e.g., "repository path is /path/to/repo")
        - Names or identifiers (e.g., "the project is called X")
        - URLs or endpoints
        - Specific values or configurations mentioned
        - Any other concrete facts that would be useful context

        Do NOT extract:
        - The goals or objectives themselves (these are desires, not beliefs)
        - Inferred or assumed information not explicitly stated
        - Vague or subjective statements

        IMPORTANT: Each belief MUST have exactly these three fields:
        - "name": A concise identifier string (e.g., "repo_path", "project_name", "target_url")
        - "value": The actual value as a string (e.g., "/path/to/repo", "my-project", "https://api.example.com")
        - "certainty": A float between 0.0 and 1.0 (use 1.0 for explicitly stated facts)

        Example of CORRECT format:
        {{
          "beliefs": [
            {{"name": "repo_path", "value": "/Users/douglas/code/masters/pydantic-ai-bdi", "certainty": 1.0}},
            {{"name": "repo_name", "value": "pydantic-ai-bdi", "certainty": 1.0}}
          ],
          "explanation": "Extracted repository path and name from desire description."
        }}

        Example of INCORRECT format (DO NOT USE):
        {{
          "beliefs": [{{"repo_path": "/path", "repo_name": "project"}}]
        }}

        If no factual information can be extracted, return an empty beliefs list with an explanation.
        """
    )


def build_planning_stage1_prompt(desires_text: str, beliefs_text: str) -> str:
    return dedent(
        f"""
        Given the following overall desires and current beliefs, identify high-level intentions required to fulfill these desires.
        For each relevant desire, propose one or more concise intentions. Each intention should represent a distinct goal or task achievable *by you, the AI agent*.

        Focus ONLY on WHAT needs to be done at a high level, but ensure these goals are achievable through information processing, analysis, or using the available tools.
        Do *not* propose intentions that require physical actions in the real world (e.g., installing hardware), direct interaction with physical systems beyond your tool capabilities, or capabilities you do not possess based on the available tools.

        Overall Desires:
        {desires_text}

        Current Beliefs:
        {beliefs_text}

        Available Tools:
        (The underlying Pydantic AI agent will provide the available tools, including those from MCP, to the LLM.)

        Respond with a list of high-level intentions using the required format. Associate each intention with its corresponding desire ID.
        """
    )


def build_planning_stage2_prompt(
    intention_description: str,
    desire_id: str,
    beliefs_text: str,
) -> str:
    return dedent(
        f"""
        Your task is to create a detailed, step-by-step action plan to achieve the following high-level intention:
        '{intention_description}' (This contributes to overall Desire ID: {desire_id})

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
        Focus exclusively on HOW to achieve the intention '{intention_description}' using only the allowed action types.
        Provide parameters for tool calls based on the context and beliefs.
        """
    )


def build_step_belief_extraction_prompt(
    step_description: str,
    step_result: str,
    step_success: bool,
) -> str:
    return dedent(
        f"""
        Analyze the following step execution and extract any factual information that should be recorded as beliefs.

        Step Objective: "{step_description}"
        Step Result: "{step_result}"
        Step Success: {step_success}

        Extract beliefs about:
        - Factual information discovered (e.g., file paths, status values, API responses)
        - Error causes or constraints (e.g., "path does not exist", "network unavailable")
        - State changes or conditions revealed (e.g., "repository is empty", "file contains X")
        - Tool availability or limitations learned (e.g., "tool requires parameter Y")

        For FAILED steps, focus on extracting information about WHY it failed - these constraints are valuable.
        For SUCCESSFUL steps, extract the positive information discovered.

        IMPORTANT: Each belief MUST have exactly these three fields:
        - "name": A concise identifier string (e.g., "repo_path", "commit_count", "error_type")
        - "value": The actual value as a string (e.g., "/path/to/repo", "42", "permission_denied")
        - "certainty": A float between 0.0 and 1.0 indicating confidence

        Example of CORRECT format:
        {{
          "beliefs": [
            {{"name": "repo_path", "value": "/Users/douglas/code/project", "certainty": 1.0}},
            {{"name": "has_commits", "value": "true", "certainty": 0.9}}
          ],
          "explanation": "Extracted repository path and confirmed commits exist."
        }}

        Example of INCORRECT format (DO NOT USE):
        {{
          "beliefs": [{{"repo_path": "/path", "has_commits": true}}]
        }}

        If no meaningful beliefs can be extracted, return an empty beliefs list with an explanation.
        """
    )


def build_step_assessment_prompt(
    step_description: str,
    result_output: str,
    step_type: str,
    history_context: str,
) -> str:
    return dedent(
        f"""
        Original objective for the step: "{step_description}"
        Result obtained: "{result_output}"
        Step type: {step_type}

        Recent step history:
        {history_context}

        Evaluate if the step successfully achieved its original objective.

        Assessment Guidelines:

        FOR TOOL CALL STEPS:
        - If the tool executed and returned data (not an error message), mark as SUCCESS
        - The result may include analysis or discussion of the data - this is normal and doesn't indicate failure
        - Only mark as FAILED if the tool returned an error, exception, or "not found" type message

        FOR CHECK/VERIFY STEPS:
        - If the result provides a definitive answer (yes/no, found/not found, true/false), mark as SUCCESS

        FOR DESCRIPTIVE STEPS (no tool call):
        - If the step produced a concrete outcome or information, mark as SUCCESS
        - If the step only discussed what should be done without doing it, mark as FAILED

        FOR ALL STEPS:
        - Ignore verbose explanations or analysis in the result - focus on whether the objective was met
        - If the result explicitly states an error occurred, mark as FAILED
        - If uncertain, prefer SUCCESS over FAILURE (be lenient)

        Provide your assessment:
        - success: true if the step achieved its objective, false if it clearly failed
        - reason: brief explanation (especially important if failed)
        """
    )


def build_tool_execution_prompt(
    beliefs_context: str,
    retry_context: str,
    tool_name: str,
    tool_params: dict[str, Any],
    is_retry: bool,
) -> str:
    retry_warning = (
        "IMPORTANT: Previous attempts failed. Review the failure information above and modify your approach."
        if is_retry
        else ""
    )
    return dedent(
        f"""
        Current known information (beliefs):
        {beliefs_context}
        {retry_context}
        Execute the tool '{tool_name}' with the suggested parameters: {tool_params}

        You may adjust parameters if current beliefs suggest better values or if conditions have changed.
        {retry_warning}
        Perform this action now.
        """
    )


def build_descriptive_execution_prompt(
    beliefs_context: str,
    retry_context: str,
    task_description: str,
    is_retry: bool,
) -> str:
    retry_warning = (
        "IMPORTANT: Previous attempts failed. Review the failure information above and modify your approach."
        if is_retry
        else ""
    )
    return dedent(
        f"""
        Current known information (beliefs):
        {beliefs_context}
        {retry_context}
        Task: {task_description}

        Consider the current beliefs when executing this task.
        {retry_warning}
        """
    )


def build_reconsideration_prompt(
    beliefs_text: str,
    history_context: str,
    desire_id: str,
    remaining_steps_text: str,
) -> str:
    return dedent(
        f"""
        Current Agent Beliefs:
        {beliefs_text}

        Step History:
        {history_context}

        Remaining Plan Steps (for Desire ID '{desire_id}'):
        {remaining_steps_text}

        Evaluate whether the remaining plan should continue or needs revision.

        Provide your assessment as:
        - valid: true if the plan seems sound to continue, false if it needs revision
        - reason: if valid is false, provide a brief explanation of why the plan is flawed

        Consider:
        1. Is this remaining plan still likely to succeed in achieving the original desire '{desire_id}'?
        2. Are there patterns in the step history suggesting the plan needs adjustment?
        3. Are there contradictions between beliefs, history, and the plan's assumptions?
        4. Based on the history of successful and failed steps, should the plan be modified?
        """
    )


def build_hitl_interpretation_prompt(
    failure_context: dict[str, Any],
    user_nl_instruction: str,
    tools_description_for_llm: str,
) -> str:
    return dedent(
        f"""
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
           * File paths (e.g., "the repo is at /path/to/repo" -> belief: repo_path = "/path/to/repo")
           * Status values (e.g., "the service is offline" -> belief: service_status = "offline")
           * Configuration values (e.g., "use port 8080" -> belief: server_port = "8080")
           * Constraints (e.g., "that API requires authentication" -> belief: api_requires_auth = "true")
           * Error causes (e.g., "path doesn't exist" -> belief: path_invalid = "true")

        Plan Manipulation:
        4. If the user suggests modifying the current step, populate 'current_step_modifications' with a dictionary of changes. For tool calls, this is often a new 'tool_params' dictionary. For descriptive steps, it might be a new 'description'.
        5. If the user suggests new steps, populate 'new_steps_definition' with a list of dictionaries. Each dictionary must conform to the IntentionStep schema (fields: description, is_tool_call, tool_name, tool_params).
           If generating tool calls, ensure 'tool_name' is valid from the available tools and 'tool_params' are appropriate.

        Summary:
        6. Provide a concise 'user_guidance_summary' explaining your interpretation, chosen action, AND any beliefs extracted.
        7. If the user's guidance is unclear, a comment, or cannot be mapped to a specific plan manipulation, use 'COMMENT_NO_ACTION' and explain in the summary (but still extract beliefs if factual information was provided).

        REMEMBER: Belief extraction and plan manipulation are ORTHOGONAL. Even when choosing MODIFY_CURRENT_AND_RETRY or RETRY_CURRENT_AS_IS, if the user provides factual information, EXTRACT IT TO BELIEFS.
        """
    )


__all__ = [
    "build_descriptive_execution_prompt",
    "build_hitl_interpretation_prompt",
    "build_initial_belief_extraction_prompt",
    "build_planning_stage1_prompt",
    "build_planning_stage2_prompt",
    "build_reconsideration_prompt",
    "build_step_assessment_prompt",
    "build_step_belief_extraction_prompt",
    "build_tool_execution_prompt",
]
