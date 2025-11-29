"""Reconsideration-related schemas for the BDI agent.

This module contains data models for plan reconsideration and validity assessment.
"""

from typing import Optional
from pydantic import BaseModel


class ReconsiderResult(BaseModel):
    """Result of plan reconsideration assessment."""

    valid: bool
    reason: str | None = None


class StepAssessmentResult(BaseModel):
    """Result of step success assessment."""

    success: bool
    reason: str | None = None


__all__ = [
    "ReconsiderResult",
    "StepAssessmentResult",
]
