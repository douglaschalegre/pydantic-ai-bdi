from typing import (
    Dict,
    List,
    Any,
    Optional,
    Callable,
    Literal,
)
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class Belief(BaseModel):
    """Represents a piece of information the agent holds about the world."""

    name: str
    value: Any
    source: str
    timestamp: float
    certainty: float = 1.0


class BeliefSet:
    """Manages the agent's beliefs."""

    def __init__(self):
        self.beliefs: Dict[str, Belief] = {}

    def add(self, belief: Belief):
        """Add or update a belief."""
        self.beliefs[belief.name] = belief

    def get(self, name: str) -> Optional[Belief]:
        """Retrieve a belief by name."""
        return self.beliefs.get(name)

    def update(self, name: str, value: Any, source: str, certainty: float = 1.0):
        """Update an existing belief or add if new."""
        if name in self.beliefs:
            self.beliefs[name].value = value
            self.beliefs[name].source = source
            self.beliefs[name].timestamp = datetime.now().timestamp()
            self.beliefs[name].certainty = certainty
        else:
            self.add(
                Belief(
                    name=name,
                    value=value,
                    source=source,
                    timestamp=datetime.now().timestamp(),
                    certainty=certainty,
                )
            )

    def remove(self, name: str):
        """Remove a belief."""
        if name in self.beliefs:
            del self.beliefs[name]


class DesireStatus(Enum):
    """Status of a desire."""

    PENDING = "pending"
    ACTIVE = "active"
    ACHIEVED = "achieved"
    FAILED = "failed"


class Desire(BaseModel):
    """Represents a high-level goal or objective for the agent."""

    id: str
    description: str
    priority: float = Field(ge=0.0, le=1.0, default=0.5)
    status: DesireStatus = DesireStatus.PENDING
    created_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    achieved_at: Optional[float] = None

    def update_status(self, new_status: DesireStatus, logger: Callable):
        self.status = new_status
        if new_status == DesireStatus.ACHIEVED:
            self.achieved_at = datetime.now().timestamp()
        logger(
            types=["desires"],
            message=f"Desire '{self.id}' status updated to {new_status}",
        )


class IntentionStep(BaseModel):
    """A single step within an intention."""

    description: str = Field(
        description="Detailed description of the step (HOW to perform it). Can be natural language or a tool call hint."
    )
    is_tool_call: bool = Field(
        default=False,
        description="Set to true if this step involves calling a specific tool.",
    )
    tool_name: Optional[str] = Field(
        default=None,
        description="The name of the tool to call, if is_tool_call is true.",
    )
    tool_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Parameters for the tool call, if is_tool_call is true.",
    )


class StepHistory(BaseModel):
    """Tracks the history of executed steps and their outcomes."""

    step_description: str
    step_number: int
    result: str
    success: bool
    timestamp: float
    beliefs_updated: Dict[str, Any]


class Intention(BaseModel):
    """Represents a committed plan of action (sequence of steps) to achieve a desire."""

    desire_id: str
    description: str | None = Field(
        default=None,
        description="High-level intention description (WHAT to achieve), separate from current executing step.",
    )
    steps: List[IntentionStep]
    current_step: int = 0
    step_history: List[StepHistory] = []

    def increment_current_step(self, logger: Callable):
        self.current_step += 1
        logger(
            types=["intentions"],
            message=f"Intention for desire '{self.desire_id}' advanced to step {self.current_step}",
        )

    def add_to_history(
        self,
        step: IntentionStep,
        result: str,
        success: bool,
        beliefs_updated: Dict[str, Any],
    ):
        """Adds a step execution to the history."""
        self.step_history.append(
            StepHistory(
                step_description=step.description,
                step_number=self.current_step,
                result=result,
                success=success,
                timestamp=datetime.now().timestamp(),
                beliefs_updated=beliefs_updated,
            )
        )


class HighLevelIntention(BaseModel):
    desire_id: str = Field(
        description="The ID of the desire this intention relates to."
    )
    description: str = Field(
        description="A concise, high-level description of the intention (WHAT to achieve)."
    )


class HighLevelIntentionList(BaseModel):
    """A list of high-level intentions, expected output from Stage 1."""

    intentions: List[HighLevelIntention]


class DetailedStepList(BaseModel):
    """A list of detailed steps, expected output from Stage 2."""

    steps: List[IntentionStep]


class ReconsiderResult(BaseModel):
    valid: bool
    reason: str | None = None


class ExtractedBelief(BaseModel):
    """Represents a belief extracted from a step execution result."""

    name: str = Field(
        description="A concise identifier for the belief (e.g., 'git_repo_path', 'network_status', 'file_exists')"
    )
    value: str = Field(
        description="The value or content of the belief (e.g., '/actual/path', 'offline', 'true')"
    )
    certainty: float = Field(
        ge=0.0,
        le=1.0,
        default=0.8,
        description="Confidence level in this belief (0.0 = uncertain, 1.0 = certain)",
    )


class BeliefExtractionResult(BaseModel):
    """Result of extracting beliefs from a step execution outcome."""

    beliefs: List[ExtractedBelief] = Field(
        default=[],
        description="List of beliefs extracted from the step result",
    )
    explanation: str = Field(
        description="Brief explanation of what information was extracted and why these beliefs are relevant"
    )


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
    "Belief",
    "BeliefSet",
    "Desire",
    "DesireStatus",
    "Intention",
    "IntentionStep",
    "HighLevelIntentionList",
    "DetailedStepList",
    "ReconsiderResult",
    "PlanManipulationDirective",
    "ExtractedBelief",
    "BeliefExtractionResult",
]
