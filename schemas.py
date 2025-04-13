from typing import (
    Dict,
    List,
    Any,
    Optional,
    TypeVar,
    Generic,
    Callable,
    Awaitable,
    Literal,
    Type,
)
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from pydantic_ai.agent import RunResultDataT


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


class IntentionStep(BaseModel):
    """A single step within an intention."""

    description: str = Field(
        description="Detailed description of the step (HOW to perform it). Can be natural language or a tool call hint."
    )
    is_tool_call: bool = Field(
        default=False,
        description="Set to true if this step involves calling a specific tool.",
    )
    tool_name: Optional[str] = Field(
        default=None,
        description="The name of the tool to call, if is_tool_call is true.",
    )
    tool_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Parameters for the tool call, if is_tool_call is true.",
    )


class Intention(BaseModel):
    """Represents a committed plan of action (sequence of steps) to achieve a desire."""

    desire_id: str  # The desire this intention aims to fulfill
    steps: List[IntentionStep]
    current_step: int = 0

    def increment_current_step(self, logger: Callable):
        self.current_step += 1
        logger(
            types=["intentions"],
            message=f"Intention for desire '{self.desire_id}' advanced to step {self.current_step}",
        )


# --- LLM Response Models for Intention Generation ---


class HighLevelIntention(BaseModel):
    desire_id: str = Field(
        description="The ID of the desire this intention relates to."
    )
    description: str = Field(
        description="A concise, high-level description of the intention (WHAT to achieve)."
    )


class HighLevelIntentionList(BaseModel):
    """A list of high-level intentions, expected output from Stage 1."""

    intentions: List[HighLevelIntention]


class DetailedStepList(BaseModel):
    """A list of detailed steps, expected output from Stage 2."""

    steps: List[IntentionStep]


# LLM Response Models for Reconsideration
class ReconsiderResult(BaseModel):
    valid: bool
    reason: str | None = None
