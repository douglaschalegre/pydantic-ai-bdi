"""BDI (Belief-Desire-Intention) Agent Framework.

A modular BDI agent implementation built on Pydantic AI, with support for:
- Belief management and extraction
- Desire-driven planning
- Two-stage intention generation
- Step-by-step execution with outcome analysis
- Plan reconsideration and monitoring
- Human-in-the-loop intervention

Main exports:
- BDI: The main agent class
- Belief, BeliefSet, Desire, DesireStatus, Intention, IntentionStep: Core schemas
"""

# Main agent class
from bdi.agent import BDI

# Core schemas (most commonly used)
from bdi.schemas import (
    Belief,
    BeliefSet,
    Desire,
    DesireStatus,
    Intention,
    IntentionStep,
    # Also export other useful schemas
    HighLevelIntentionList,
    DetailedStepList,
    ReconsiderResult,
    BeliefExtractionResult,
    PlanManipulationDirective,
)

__all__ = [
    # Agent
    "BDI",
    # Core schemas
    "Belief",
    "BeliefSet",
    "Desire",
    "DesireStatus",
    "Intention",
    "IntentionStep",
    # Additional schemas
    "HighLevelIntentionList",
    "DetailedStepList",
    "ReconsiderResult",
    "BeliefExtractionResult",
    "PlanManipulationDirective",
]
