"""Reconsideration-related schemas for the BDI agent.

This module contains data models for plan reconsideration and validity assessment.
"""

from typing import Optional
from pydantic import BaseModel


class ReconsiderResult(BaseModel):
    """Result of plan reconsideration assessment."""

    valid: bool
    reason: str | None = None


__all__ = [
    "ReconsiderResult",
]
