"""Desire-related schemas for the BDI agent.

This module contains data models for representing desires (high-level goals)
and their lifecycle status.
"""

from typing import Optional, Callable
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


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


__all__ = [
    "Desire",
    "DesireStatus",
]
