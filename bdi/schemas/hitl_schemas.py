"""Human-in-the-loop (HITL) related schemas for the BDI agent.

This module contains data models for HITL interaction, including plan manipulation
directives that structure how the agent should respond to user guidance.
"""

from typing import Dict, List, Any, Optional, Literal
from pydantic import BaseModel, Field


class PlanManipulationDirective(BaseModel):
    """
    Defines the structured directive for how the BDI agent should manipulate
    its current plan based on interpreted user guidance during a HITL interaction.
    """

    manipulation_type: Literal[
        "RETRY_CURRENT_AS_IS",  # No change, just retry the current step
        "MODIFY_CURRENT_AND_RETRY",  # Change params/desc of current step and retry
        "REPLACE_CURRENT_STEP_WITH_NEW",  # Replace current step(s) with new one(s)
        "INSERT_NEW_STEPS_BEFORE_CURRENT",  # Add new step(s) before the current one
        "INSERT_NEW_STEPS_AFTER_CURRENT",  # Add new step(s) immediately after current one (less common, but possible)
        "REPLACE_REMAINDER_OF_PLAN",  # Discard rest of plan, use new steps
        "SKIP_CURRENT_STEP",  # Advance past current step
        "ABORT_INTENTION",  # Cancel the whole intention
        "UPDATE_BELIEFS_AND_RETRY",  # User provided info to update beliefs, then retry
        "COMMENT_NO_ACTION",  # User just commented, no plan change, LLM couldn't map to action
    ] = Field(
        ...,
        description="The specific type of manipulation to perform on the current plan.",
    )

    current_step_modifications: Optional[Dict[str, Any]] = Field(
        None,
        description="Modifications for the current step if manipulation_type is 'MODIFY_CURRENT_AND_RETRY'. "
        "This could be a dictionary to update fields of the IntentionStep model, "
        "e.g., {'tool_params': {'new_param': 'value'}, 'description': 'new step description'}.",
    )

    new_steps_definition: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Definitions for new steps if manipulation_type involves adding/replacing steps. "
        "Each dictionary in the list should conform to the IntentionStep schema "
        "and will be used to create new IntentionStep objects.",
    )

    beliefs_to_update: Optional[Dict[str, Dict[str, Any]]] = Field(
        None,
        description="Beliefs to add or update if manipulation_type is 'UPDATE_BELIEFS_AND_RETRY'. "
        "The key is the belief name, and the value is a dictionary conforming to the Belief schema "
        "(e.g., {'value': 'new value', 'source': 'human_guidance', 'certainty': 1.0}).",
    )

    user_guidance_summary: str = Field(
        ...,
        description="The LLM's brief summary of its understanding of the user's guidance and the rationale for the chosen manipulation.",
    )


__all__ = [
    "PlanManipulationDirective",
]
