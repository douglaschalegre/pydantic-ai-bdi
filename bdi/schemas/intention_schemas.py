"""Intention-related schemas for the BDI agent.

This module contains data models for representing intentions (committed plans),
intention steps, step history, and LLM output formats for intention generation.
"""

from typing import Dict, List, Any, Optional, Callable
from pydantic import BaseModel, Field
from datetime import datetime


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
    """High-level intention output from Stage 1 of intention generation."""

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


__all__ = [
    "IntentionStep",
    "StepHistory",
    "Intention",
    "HighLevelIntention",
    "HighLevelIntentionList",
    "DetailedStepList",
]
