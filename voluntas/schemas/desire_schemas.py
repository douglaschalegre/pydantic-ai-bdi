"""Desire-related schemas for the BDI agent.

This module contains data models for representing desires (high-level goals)
and their lifecycle status.
"""

import hashlib
from typing import Optional, Callable
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


def generate_desire_id(description: str, timestamp: float | None = None) -> str:
    """Generate a unique desire ID based on description and timestamp hash.

    Args:
        description: The desire description text
        timestamp: Optional timestamp (uses current time if not provided)

    Returns:
        A unique ID in format 'desire_<8-char-hash>'
    """
    if timestamp is None:
        timestamp = datetime.now().timestamp()
    content = f"{description}:{timestamp}"
    hash_digest = hashlib.sha256(content.encode()).hexdigest()[:8]
    return f"desire_{hash_digest}"


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
    "generate_desire_id",
]
