"""Reconsideration-related schemas for the BDI agent.

This module contains data models for plan reconsideration and validity assessment.
"""

from typing import Literal

from pydantic import BaseModel, Field

from voluntas.schemas.plan_schemas import PlanStep

PlanReconsiderationAction = Literal[
    "continue",
    "repair_plan",
    "replace_plan",
    "fail_desire",
]


class ReconsiderResult(BaseModel):
    """Structured result of plan-level reconsideration assessment."""

    action: PlanReconsiderationAction
    reason: str | None = None
    plan_steps: list[PlanStep] | None = Field(
        default=None,
        description="Replacement Plan Steps for repair_plan or replace_plan actions.",
    )


class StepAssessmentResult(BaseModel):
    """Result of step success assessment."""

    success: bool
    reason: str | None = None


class DesireSatisfactionResult(BaseModel):
    """Result of desire satisfaction assessment after an intention completes."""

    satisfied: bool
    reason: str | None = None


__all__ = [
    "DesireSatisfactionResult",
    "PlanReconsiderationAction",
    "ReconsiderResult",
    "StepAssessmentResult",
]
