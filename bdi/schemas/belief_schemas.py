"""Belief-related schemas for the BDI agent.

This module contains data models for representing beliefs, managing belief sets,
and extracting beliefs from step execution results.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


BeliefMutation = Literal["created", "updated", "unchanged"]


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

    def upsert(
        self, name: str, value: Any, source: str, certainty: float = 1.0
    ) -> BeliefMutation:
        """Insert or update a belief, returning mutation state.

        Returns:
            "created" when a new belief is added,
            "updated" when an existing belief value changes or certainty increases,
            "unchanged" when the value is the same and certainty does not improve.
        """
        existing = self.beliefs.get(name)
        if not existing:
            timestamp = datetime.now().timestamp()
            self.add(
                Belief(
                    name=name,
                    value=value,
                    source=source,
                    timestamp=timestamp,
                    certainty=certainty,
                )
            )
            return "created"

        if existing.value == value:
            if certainty <= existing.certainty:
                return "unchanged"

            timestamp = datetime.now().timestamp()
            existing.source = source
            existing.timestamp = timestamp
            existing.certainty = certainty
            return "updated"

        timestamp = datetime.now().timestamp()
        existing.value = value
        existing.source = source
        existing.timestamp = timestamp
        existing.certainty = certainty
        return "updated"

    def update(
        self, name: str, value: Any, source: str, certainty: float = 1.0
    ) -> BeliefMutation:
        """Backwards-compatible alias for belief upsert."""
        return self.upsert(name=name, value=value, source=source, certainty=certainty)

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
        default_factory=list,
        description="List of beliefs extracted from the step result",
    )
    explanation: str = Field(
        description="Brief explanation of what information was extracted and why these beliefs are relevant"
    )


class BeliefUpdateDecision(BaseModel):
    """LLM decision for resolving belief updates."""

    should_update: bool = Field(
        description="Whether the incoming belief should update the existing belief"
    )
    normalized_value: Any = Field(
        description="Canonical value to store for this belief"
    )
    certainty: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for the value that should be stored",
    )
    rationale: str = Field(
        description="Brief explanation for the update decision"
    )


class BeliefNameResolutionDecision(BaseModel):
    """LLM decision for belief name resolution."""

    resolved_name: str = Field(
        description="Final belief name to use (existing key or incoming key)",
        min_length=1,
    )
    rationale: str = Field(
        description="Brief explanation for why this belief name was selected"
    )


__all__ = [
    "Belief",
    "BeliefSet",
    "ExtractedBelief",
    "BeliefExtractionResult",
    "BeliefNameResolutionDecision",
    "BeliefUpdateDecision",
]
