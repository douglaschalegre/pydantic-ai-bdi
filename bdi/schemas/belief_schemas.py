"""Belief-related schemas for the BDI agent.

This module contains data models for representing beliefs, managing belief sets,
and extracting beliefs from step execution results.
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


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


__all__ = [
    "Belief",
    "BeliefSet",
    "ExtractedBelief",
    "BeliefExtractionResult",
]
