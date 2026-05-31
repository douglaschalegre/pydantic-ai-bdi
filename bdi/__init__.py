"""BDI (Belief-Desire-Intention) Agent Framework.

A modular BDI agent implementation built on Pydantic AI, with support for:
- Belief management and extraction
- Desire-driven planning
- Single-stage intention generation
- Step-by-step execution with outcome analysis
- Plan reconsideration and monitoring
- Human-in-the-loop intervention

Main exports:
- BDI: The main agent class
- Belief, BeliefSet, Desire, DesireStatus, Intention, Plan: Core schemas
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
    Plan,
    PlanStatus,
    PlanStep,
    PlanStepHistory,
    # Also export other useful schemas
    HighLevelIntentionList,
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
    "Plan",
    "PlanStatus",
    "PlanStep",
    "PlanStepHistory",
    # Additional schemas
    "HighLevelIntentionList",
    "ReconsiderResult",
    "BeliefExtractionResult",
    "PlanManipulationDirective",
]
