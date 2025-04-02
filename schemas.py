from pydantic import BaseModel, Field
from typing import Any, Optional, List, Dict, Callable, Literal
from enum import Enum
from pydantic_ai.agent import RunResultDataT


class Belief(BaseModel):
    """Representation of a single belief the agent holds about the world.

    Examples:
        # Create a belief about room temperature
        temp_belief = Belief(
        name="room_temperature",
        value=22.5,
        confidence=0.95,
        source="temperature_sensor",
        timestamp=datetime.now().timestamp()
        )

        # Create a belief about user presence
        presence_belief = Belief(
        name="user_present",
        value=True,
        confidence=1.0,
        source="motion_sensor"
        )
    """

    name: str
    value: Any
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    source: Optional[str] = None
    timestamp: Optional[float] = None


class BeliefSet(BaseModel):
    """Container for the agent's beliefs about the world.

    Examples:
        # Create a belief set and add beliefs
        belief_set = BeliefSet()
        belief_set.add(Belief(name="temperature", value=22.5))
        belief_set.add(Belief(name="humidity", value=45))

        # Retrieve and update beliefs
        temp = belief_set.get("temperature")
        if temp and temp.value > 25:
        print("Temperature is too high")

        # Remove outdated beliefs
        belief_set.remove("old_sensor_reading")
    """

    beliefs: Dict[str, Belief] = Field(default_factory=dict)

    def add(self, belief: Belief) -> None:
        """Add or update a belief in the belief set."""
        self.beliefs[belief.name] = belief

    def get(self, name: str) -> Optional[Belief]:
        """Get a belief by name."""
        return self.beliefs.get(name)

    def remove(self, name: str) -> None:
        """Remove a belief by name."""
        if name in self.beliefs:
            del self.beliefs[name]


class DesireStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    ACHIEVED = "achieved"
    FAILED = "failed"
    ABANDONED = "abandoned"


class Desire(BaseModel):
    """Representation of a goal the agent wants to achieve.

    Examples:
        # Create a desire to maintain optimal room temperature
        temp_desire = Desire(
        id="maintain_temp",
        description="Keep room temperature between 20-24°C",
        priority=0.8,
        preconditions=["has_temperature_reading"],
        success_conditions=["temperature_in_range"]
        )

        # Create a desire to save energy
        energy_desire = Desire(
        id="save_energy",
        description="Minimize energy consumption",
        priority=0.6,
        status=DesireStatus.ACTIVE
        )
    """

    id: str
    description: str
    priority: float = Field(ge=0.0, le=1.0, default=0.5)
    status: DesireStatus = DesireStatus.PENDING
    preconditions: List[str] = Field(default_factory=list)
    success_conditions: List[str] = Field(default_factory=list)

    def update_status(self, status: DesireStatus, log_states: Callable[[], None]):
        self.status = status
        log_states(["desires"])


class IntentionStep(BaseModel):
    """Representation of a single step in an intention's execution plan.

    An intention step can be executed either as a direct LLM prompt or as a tool call.
    """

    description: str
    tool_name: Optional[str] = None
    tool_params: Dict[str, Any] = Field(default_factory=dict)

    @property
    def is_tool_call(self) -> bool:
        """Check if this step should be executed as a tool call."""
        return self.tool_name is not None


class Intention(BaseModel):
    """Representation of an action plan to achieve a desire.

    Examples:
        # Create an intention with explicit tool calls
        adjust_temp = Intention(
            desire_id="maintain_temp",
            structured_steps=[
                IntentionStep(description="Check current temperature"),
                IntentionStep(
                    description="Adjust thermostat",
                    tool_name="adjust_thermostat",
                    tool_params={"temperature": 22.5}
                )
            ]
        )
    """

    desire_id: str
    steps: List[IntentionStep] = Field(default_factory=list)
    current_step: int = 0
    status: DesireStatus = DesireStatus.ACTIVE

    def increment_current_step(self, log_states: Callable[[], None]):
        self.current_step += 1
        log_states(["intentions"])


class ToolConfig(BaseModel):
    """Configuration for a tool that can be used by the BDI agent.

    This helps associate tools with specific BDI reasoning phases.
    """

    name: str
    description: str
    phases: List[Literal["perception", "desire", "intention", "general"]] = ["general"]
    result_type: type[RunResultDataT] | None = None
