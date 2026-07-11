"""Intention-related schemas for the BDI agent.

This module contains data models for representing intentions as commitments to
desires, plus LLM output formats for intention generation.
"""

from typing import List

from pydantic import BaseModel, Field

from voluntas.schemas.plan_schemas import IntentionStep, Plan, StepHistory


class Intention(BaseModel):
    """Represents commitment to a Desire and owns the active executable Plan."""

    desire_id: str
    description: str | None = Field(
        default=None,
        description="High-level intention description (WHAT to achieve), separate from the executing Plan.",
    )
    active_plan: Plan = Field(
        description="The executable strategy currently owned by this Intention."
    )


class HighLevelIntention(BaseModel):
    """High-level intention output from intention generation."""

    desire_id: str = Field(
        description="The ID of the desire this intention relates to."
    )
    description: str = Field(
        description="A concise, high-level description of the intention (WHAT to achieve)."
    )


class HighLevelIntentionList(BaseModel):
    """A list of high-level intentions expected from planning."""

    intentions: List[HighLevelIntention]


__all__ = [
    "IntentionStep",
    "StepHistory",
    "Plan",
    "Intention",
    "HighLevelIntention",
    "HighLevelIntentionList",
]
