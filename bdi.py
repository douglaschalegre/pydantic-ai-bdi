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
)
from enum import Enum
from pydantic import BaseModel, Field
from collections import deque
from pydantic_ai import Agent
from util import bcolors

T = TypeVar("T")


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


class Intention(BaseModel):
    """Representation of an action plan to achieve a desire.

    Examples:
        # Create an intention to adjust room temperature
        adjust_temp = Intention(
        desire_id="maintain_temp",
        steps=[
            "check_current_temperature",
            "calculate_adjustment_needed",
            "adjust_hvac_settings"
        ]
        )

        # Create an intention to handle energy saving
        save_energy = Intention(
        desire_id="save_energy",
        steps=[
            "identify_unused_devices",
            "turn_off_unnecessary_systems",
            "optimize_hvac_schedule"
        ]
        )
    """

    desire_id: str
    steps: List[str] = Field(default_factory=list)
    current_step: int = 0
    status: DesireStatus = DesireStatus.ACTIVE

    def increment_current_step(self, log_states: Callable[[], None]):
        self.current_step += 1
        log_states(["intentions"])


class BDI(Agent, Generic[T]):
    """BDI (Belief-Desire-Intention) agent implementation.

    Extends the Pydantic AI Agent with a BDI architecture that includes:
    - Beliefs: The agent's knowledge about the world
    - Desires: The agent's high-level goals
    - Intentions: The agent's committed actions to achieve its desires

    The BDI reasoning cycle involves:
    1. Updating beliefs based on perceptions
    2. Generating desires based on beliefs
    3. Forming intentions from desires
    4. Executing intentions to achieve goals

    Key extension concepts:
    - Perception handlers: Functions that process incoming information and update beliefs
    - Desire generators: Functions that create new desires based on current beliefs
    - Intention selectors: Functions that decide which desires to commit to as intentions

    This implementation uses a modular approach where handlers, generators, and selectors
    can be registered to customize the agent's behavior at each stage of the BDI cycle.

    Examples:
     Here's a simple example of creating a smart home BDI agent:

     # Create perception handler for temperature readings
     async def temp_handler(perception: dict, beliefs: BeliefSet) -> None:
         if "temperature" in perception:
             self.beliefs.add(Belief(
                 name="room_temperature",
                 value=perception["temperature"],
                 source="temp_sensor"
             ))
     # Create desire generator for temperature control
     async def temp_desire_gen(beliefs: BeliefSet) -> List[Desire]:
         temp = beliefs.get("room_temperature")
         if temp and (temp.value < 20 or temp.value > 24):
             return [Desire(
                 id="adjust_temperature",
                 description="Adjust temperature to optimal range",
                 priority=0.8
             )]
         return []
     # Create intention selector
     async def temp_intention_selector(
         desires: List[Desire],
         beliefs: BeliefSet
     ) -> List[Intention]:
         intentions = []
         for desire in desires:
             if desire.id == "adjust_temperature":
                 intentions.append(Intention(
                     desire_id=desire.id,
                     steps=["check_temp", "adjust_hvac"]
                 ))
         return intentions
     # Create and set up the agent
         agent = BDI("openai:gpt-4")
         agent.register_perception_handler(temp_handler)
         agent.register_desire_generator(temp_desire_gen)
         agent.register_intention_selector(temp_intention_selector)
     # Run the agent
         async def main():
             perception = {"temperature": 25.5}
             await agent.bdi_cycle(perception)
     asyncio.run(main())
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.beliefs = BeliefSet()
        self.desires: List[Desire] = []
        self.intentions: deque[Intention] = deque()
        self.perception_handlers: List[Callable[[Any, BeliefSet], Awaitable[None]]] = []
        self.desire_generators: List[
            Callable[[BeliefSet], Awaitable[List[Desire]]]
        ] = []
        self.intention_selectors: List[
            Callable[[List[Desire], BeliefSet], Awaitable[List[Intention]]]
        ] = []

    async def update_beliefs(self, perception: Any) -> None:
        """Update agent beliefs based on new perceptions.

        Args:
            perception: New information to incorporate into beliefs

        Examples:
             # Update beliefs with temperature reading
             async def example():
                 agent = BDI("openai:gpt-4")

                 async def temp_handler(data: dict, beliefs: BeliefSet):
                     beliefs.add(Belief(
                         name="temperature",
                         value=data["temperature"]
                     ))

                 agent.register_perception_handler(temp_handler)
                 await agent.update_beliefs({"temperature": 23.5})

                 temp_belief = agent.beliefs.get("temperature")
                 assert temp_belief.value == 23.5
        """
        for handler in self.perception_handlers:
            await handler(perception, self.beliefs)
        self.log_states(["beliefs"])

    async def generate_desires(self) -> None:
        """Generate new desires based on current beliefs.

        Examples:
             # Generate desires based on temperature
             async def example():
                 agent = BDI("openai:gpt-4")

                 async def temp_desire_gen(beliefs: BeliefSet) -> List[Desire]:
                     temp = beliefs.get("temperature")
                     if temp and temp.value > 24:
                         return [Desire(
                             id="cool_room",
                             description="Lower room temperature",
                             priority=0.8
                         )]
                     return []

                 agent.register_desire_generator(temp_desire_gen)
                 agent.beliefs.add(Belief(
                     name="temperature",
                     value=25
                 ))

                 await agent.generate_desires()
                 assert len(agent.desires) == 1
                 assert agent.desires[0].id == "cool_room"
        """
        new_desires = []

        # Generate desires using all registered generators
        for generator in self.desire_generators:
            desires = await generator(self.beliefs)
            new_desires.extend(desires)

        # Merge with existing desires, avoiding duplicates
        existing_ids = {
            d.id
            for d in self.desires
            if d.status in [DesireStatus.PENDING, DesireStatus.ACTIVE]
        }

        for desire in new_desires:
            if desire.id not in existing_ids:
                self.desires.append(desire)

        self.log_states(["desires"])

    async def form_intentions(self) -> None:
        """Select and prioritize intentions from current desires.

        Examples:
             # Form intentions for temperature control
             async def example():
                 agent = BDI("openai:gpt-4")

                 # Add a desire
                 agent.desires.append(Desire(
                     id="cool_room",
                     description="Lower room temperature",
                     priority=0.8
                 ))

                 async def temp_intention_selector(
                     desires: List[Desire],
                     beliefs: BeliefSet
                 ) -> List[Intention]:
                     return [Intention(
                         desire_id="cool_room",
                         steps=["check_ac", "adjust_temperature"]
                     )]

                 agent.register_intention_selector(temp_intention_selector)
                 await agent.form_intentions()

                 assert len(agent.intentions) == 1
                 assert agent.intentions[0].steps == ["check_ac", "adjust_temperature"]
        """
        active_desires = [
            d
            for d in self.desires
            if d.status in [DesireStatus.PENDING, DesireStatus.ACTIVE]
        ]

        all_intentions = []
        for selector in self.intention_selectors:
            intentions = await selector(active_desires, self.beliefs)
            all_intentions.extend(intentions)

        self.intentions.clear()
        for intention in sorted(
            all_intentions,
            key=lambda i: next(
                (d.priority for d in active_desires if d.id == i.desire_id), 0.0
            ),
            reverse=True,
        ):
            self.intentions.append(intention)

        self.log_states(["intentions"])

    async def execute_intentions(self) -> None:
        """Execute the current intentions.

        Examples:
             # Execute temperature adjustment intention
             async def example():
                 agent = BDI("openai:gpt-4")

                 # Add an intention
                 agent.intentions.append(Intention(
                     desire_id="cool_room",
                     steps=["check_ac", "adjust_temperature"]
                 ))

                 await agent.execute_intentions()

                 # After execution, the intention should advance or complete
                 assert (
                     len(agent.intentions) == 0  # Completed
                     or agent.intentions[0].current_step > 0  # Advanced
                 )
        """
        if not self.intentions:
            return

        # Get the highest priority intention (first in deque)
        intention = self.intentions[0]

        # Check if there are steps to execute
        while intention.current_step < len(intention.steps):
            print(
                f"{bcolors.OKCYAN}Executing step: {intention.steps[intention.current_step]}{bcolors.ENDC}"
            )
            # TODO:
            # Execute current step (in a real implementation, this would do something)
            # For now, just increment the step
            intention.increment_current_step(self.log_states)
            if intention.current_step >= len(intention.steps):
                for desire in self.desires:
                    if desire.id == intention.desire_id:
                        desire.update_status(DesireStatus.ACHIEVED, self.log_states)
                        break

        self.intentions.popleft()
        self.log_states(["intentions"])

    async def bdi_cycle(self, perception: Any = None) -> None:
        """Run one BDI reasoning cycle.

        Args:
            perception: Optional new information to process

        Examples:
             # Complete BDI cycle for temperature control
             async def example():
                 agent = BDI("openai:gpt-4")

                 # Register handlers
                 async def temp_handler(data: dict, beliefs: BeliefSet):
                     beliefs.add(Belief(name="temperature", value=data["temperature"]))

                 async def temp_desire_gen(beliefs: BeliefSet) -> List[Desire]:
                     temp = beliefs.get("temperature")
                     if temp and temp.value > 24:
                         return [Desire(id="cool_room", priority=0.8)]
                     return []

                 async def temp_intention_selector(
                     desires: List[Desire],
                     beliefs: BeliefSet
                 ) -> List[Intention]:
                     return [Intention(
                         desire_id="cool_room",
                         steps=["adjust_ac"]
                     )]

                 agent.register_perception_handler(temp_handler)
                 agent.register_desire_generator(temp_desire_gen)
                 agent.register_intention_selector(temp_intention_selector)

                 # Run cycle with new temperature reading
                 await agent.bdi_cycle({"temperature": 25})

                 # Verify cycle results
                 assert agent.beliefs.get("temperature").value == 25
                 assert len(agent.desires) == 1
                 assert agent.desires[0].id == "cool_room"
        """
        self.log_states(
            types=["beliefs", "desires", "intentions"],
            message="States before starting BDI cycle",
        )
        print(f"{bcolors.HEADER}\nBDI cycle starting...{bcolors.ENDC}")

        if perception:
            await self.update_beliefs(perception)
        await self.generate_desires()
        await self.form_intentions()
        await self.execute_intentions()

    def register_perception_handler(
        self, handler: Callable[[Any, BeliefSet], Awaitable[None]]
    ) -> None:
        """Register a handler for processing perceptions into beliefs.
        Perception handlers are functions that take incoming information (perceptions)
        and update the agent's beliefs accordingly. They determine how raw data is
        interpreted and incorporated into the agent's knowledge of the world.
        Args:
            handler: An async function that processes a perception and updates the belief set.
                    It takes two arguments: the perception object and the current belief set.
        """
        self.perception_handlers.append(handler)

    def register_desire_generator(
        self, generator: Callable[[BeliefSet], Awaitable[List[Desire]]]
    ) -> None:
        """Register a generator for creating desires from beliefs.
        Desire generators are functions that examine the agent's current beliefs
        and create appropriate desires (goals). They implement the motivational aspect
        of the agent by determining what the agent should want to achieve based on
        its current understanding of the world.
        Args:
            generator: An async function that generates desires based on current beliefs.
                      It takes the belief set as input and returns a list of new desires.
        """
        self.desire_generators.append(generator)

    def register_intention_selector(
        self, selector: Callable[[List[Desire], BeliefSet], Awaitable[List[Intention]]]
    ) -> None:
        """Register a selector for forming intentions from desires.
        Intention selectors are functions that decide which desires the agent should
        commit to pursuing. They implement the deliberative aspect of the agent by
        choosing which goals to actively work toward and creating action plans (intentions)
        to achieve those goals. Selectors consider factors like desire priority,
        feasibility given current beliefs, and resource constraints.
        Args:
            selector: An async function that selects desires to become intentions.
                     It takes the list of active desires and belief set as input
                     and returns a list of intentions to be pursued.
        """
        self.intention_selectors.append(selector)

    def log_states(
        self,
        types: list[Literal["beliefs", "desires", "intentions"]],
        message: str | None = None,
    ):
        if message:
            print(f"{bcolors.HEADER}{message}{bcolors.ENDC}")
        if "beliefs" in types:
            print(f"{bcolors.OKGREEN}Beliefs: {self.beliefs.beliefs}{bcolors.ENDC}")
        if "desires" in types:
            print(f"{bcolors.OKCYAN}Desires: {self.desires}{bcolors.ENDC}")
        if "intentions" in types:
            print(f"{bcolors.WARNING}Intentions: {list(self.intentions)}{bcolors.ENDC}")
