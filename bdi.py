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
from collections import deque
from pydantic_ai import Agent
from pydantic_ai.tools import AgentDepsT
from pydantic_ai.agent import RunResultDataT
from util import bcolors
from schemas import (
    Belief,
    BeliefSet,
    Desire,
    DesireStatus,
    Intention,
    ToolConfig,
    IntentionStep,
)
import re

T = TypeVar("T")

__all__ = ["BDI", "Belief", "BeliefSet", "Desire", "Intention", "IntentionStep"]


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
    It also integrates with Pydantic AI's tool system to allow tool calls during reasoning.

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

    def __init__(
        self, *args, desires: List[str] = None, intentions: List[str] = None, **kwargs
    ):
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
        self.tool_configs: Dict[str, ToolConfig] = {}

        # Initialize with string-based desires and intentions
        if desires:
            self._initialize_string_desires(desires)
        if intentions:
            self._initialize_string_intentions(intentions)

    def _initialize_string_desires(self, desire_strings: List[str]) -> None:
        """Initialize desires from string descriptions."""
        for i, desire_string in enumerate(desire_strings):
            # Create a simple desire ID based on a slug of the desire
            desire_id = f"desire_{i + 1}"

            # Create a basic desire with the string as description
            desire = Desire(
                id=desire_id,
                description=desire_string,
                priority=0.5,  # Default priority
            )
            self.desires.append(desire)
        self.log_states(["desires"])

    def _initialize_string_intentions(self, intention_strings: List[str]) -> None:
        """Initialize intentions from string descriptions."""
        for i, intention_string in enumerate(intention_strings):
            # For each intention string, we need to create a structured intention
            # that can be executed by the agent

            # First, determine which desire this intention is associated with
            # In this simple implementation, we'll just associate with the first desire
            desire_id = self.desires[0].id if self.desires else f"auto_desire_{i + 1}"

            # Create an intention with a prompt step that will rely on the LLM
            # to interpret the intention string and take appropriate actions
            intention = Intention(
                desire_id=desire_id,
                steps=[
                    IntentionStep(
                        description=f"Execute the intention: {intention_string}",
                        # No explicit tool name - this will be sent to the LLM
                    )
                ],
            )

            self.intentions.append(intention)
        self.log_states(["intentions"])

    async def generate_intentions_from_desires(self) -> None:
        """Convert string-based desires to more specific intentions using the LLM."""
        if not self.desires or self.intentions:
            # Skip if we have no desires or already have intentions
            return

        # Use the LLM to generate intentions based on desires and current beliefs
        desires_text = "\n".join([f"- {d.description}" for d in self.desires])

        # Get current beliefs as context
        beliefs_text = "\n".join(
            [
                f"- {name}: {belief.value}"
                for name, belief in self.beliefs.beliefs.items()
            ]
        )

        # Get available tools
        tools_text = "\n".join(
            [
                f"- {name}: {config.description}"
                for name, config in self.tool_configs.items()
            ]
        )

        # Prompt the LLM to generate intentions
        prompt = f"""
        Based on the following desires and current beliefs, generate specific intentions
        that can help achieve these desires. Each intention should be executable using 
        the available tools.
        
        Desires:
        {desires_text}
        
        Current Beliefs:
        {beliefs_text}
        
        Available Tools:
        {tools_text}
        
        For each desire, provide one or more intentions in the following format:

        Intention(
            desire_id=<desire_id>,
            structured_steps=[
                IntentionStep(description=<step_description>),
                IntentionStep(
                    description=<step_description>,
                    tool_name=<tool_name>,
                    tool_params=<tool_params>
                )
            ]
        )
        ...
        """

        # Run the prompt through the LLM
        result = await self.run(prompt, result_type=Intention)
        intention_plan = result.content

        # Parse the LLM's response to create intention objects
        # This is a simple parser that could be improved
        intention_sections = intention_plan.split("Intention:")

        for section in intention_sections[1:]:  # Skip the first empty section
            lines = section.strip().split("\n")
            intention_description = lines[0].strip()
            steps = []

            # Find the Steps section
            steps_start = -1
            for i, line in enumerate(lines):
                if line.strip().startswith("Steps:"):
                    steps_start = i
                    break

            if steps_start >= 0:
                # Parse steps
                for step_line in lines[steps_start + 1 :]:
                    step_line = step_line.strip()
                    if not step_line or not any(c.isdigit() for c in step_line[:2]):
                        continue

                    # Remove the numbering
                    step_text = (
                        step_line[2:].strip()
                        if step_line[1] == "."
                        else step_line[1:].strip()
                    )

                    # Check if there's a tool call
                    tool_name = None
                    tool_params = {}

                    if "[tool_name:" in step_text and "]" in step_text:
                        tool_part = step_text[step_text.find("[tool_name:") :]
                        step_desc = step_text[: step_text.find("[tool_name:")].strip()

                        # Extract tool name
                        tool_match = re.search(r"\[tool_name:\s*([^,\]]+)", tool_part)
                        if tool_match:
                            tool_name = tool_match.group(1).strip()

                        # Extract parameters if any
                        params_match = re.search(r"parameters:\s*([^\]]+)", tool_part)
                        if params_match:
                            params_text = params_match.group(1).strip()
                            # Simple key-value parsing - could be improved
                            param_pairs = params_text.split(",")
                            for pair in param_pairs:
                                if ":" in pair:
                                    k, v = pair.split(":", 1)
                                    tool_params[k.strip()] = v.strip()
                    else:
                        step_desc = step_text

                    steps.append(
                        IntentionStep(
                            description=step_desc,
                            tool_name=tool_name,
                            tool_params=tool_params,
                        )
                    )

            # Create the intention and add it to the queue
            if steps:
                # Associate with a relevant desire if possible
                matched_desire = None
                for desire in self.desires:
                    # Simple text matching - could be improved
                    if any(
                        word in intention_description.lower()
                        for word in desire.description.lower().split()
                    ):
                        matched_desire = desire
                        break

                desire_id = matched_desire.id if matched_desire else "auto_desire"
                self.intentions.append(Intention(desire_id=desire_id, steps=steps))

        self.log_states(["intentions"])

    def bdi_tool(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        phases: List[Literal["perception", "desire", "intention", "general"]] = [
            "general"
        ],
        result_type: type[RunResultDataT] | None = None,
        **tool_kwargs,
    ):
        """Register a tool specifically for the BDI agent with phase information.

        This decorator combines the standard Agent.tool decorator with BDI-specific
        configuration like which reasoning phases the tool should be available for.

        Args:
            name: The name of the tool
            description: The description of the tool
            phases: BDI reasoning phases where this tool should be available
            **tool_kwargs: Additional arguments to pass to the Agent.tool decorator

        Examples:
            # Register a tool for updating beliefs during perception
            @agent.bdi_tool(phases=["perception"])
            async def update_temperature(ctx: RunContext, temperature: float) -> None:
                ctx.beliefs.add(Belief(name="temperature", value=temperature))

            # Register a tool for checking conditions during desire generation
            @agent.bdi_tool(phases=["desire"])
            async def check_energy_usage(ctx: RunContext) -> float:
                # Check current energy consumption
                return 450.75

            # Register a tool for executing actions during intention execution
            @agent.bdi_tool(phases=["intention"])
            async def adjust_thermostat(ctx: RunContext, temperature: float) -> bool:
                # Connect to smart thermostat API and set temperature
                return True
        """

        def decorator(func):
            # Register with the standard Agent.tool decorator
            tool_name = name or func.__name__
            tool_desc = description or func.__doc__ or ""

            # Store BDI-specific configuration
            self.tool_configs[tool_name] = ToolConfig(
                name=tool_name,
                description=tool_desc,
                phases=phases,
                result_type=result_type,
            )

            # Register with the standard Agent.tool decorator
            return self.tool(name=tool_name, **tool_kwargs)(func)

        return decorator

    def get_phase_tools(
        self, phase: Literal["perception", "desire", "intention", "general"]
    ) -> List[str]:
        """Get the names of tools available for a specific BDI reasoning phase.

        Args:
            phase: The BDI reasoning phase

        Returns:
            List of tool names available for the specified phase
        """
        return [
            name
            for name, config in self.tool_configs.items()
            if phase in config.phases or "general" in config.phases
        ]

    async def call_tool(
        self,
        tool_name: str,
        tool_params: Dict[str, Any],
        phase: Literal["perception", "desire", "intention", "general"] = "general",
        deps: AgentDepsT = None,
        result_type: type[RunResultDataT] | None = None,
        prompt_suffix: str | None = None,
    ) -> Any:
        """Directly call a tool by name with the specified parameters.

        This allows BDI components to utilize the registered tools without
        going through the LLM.

        Args:
            tool_name: Name of the tool to call
            tool_params: Parameters to pass to the tool
            phase: The BDI reasoning phase making the call (for validation)
            deps: Optional dependencies to pass to the tool

        Returns:
            The result of the tool call

        Raises:
            ValueError: If the tool is not available for the specified phase
        """
        # Verify the tool is available for this phase
        if tool_name not in self.get_phase_tools(phase):
            raise ValueError(
                f"Tool '{tool_name}' is not available for the '{phase}' phase"
            )

        # Create a custom prompt that will trigger the tool
        system_prompt = """IMPORTANT: When processing tool results, DO NOT modify any values unless explicitly instructed to do so.

Your role is to facilitate communication between system components, NOT to modify data.
The exact preservation of values is critical for the system's proper functioning.
        """
        tool_call_prompt = f"{system_prompt}\n\nCall the {tool_name} tool with parameters: {tool_params}. {prompt_suffix}"

        # Execute the tool call through the agent's run method
        # This preserves all the tool's error handling and validation
        result = await self.run(tool_call_prompt, deps=deps, result_type=result_type)
        return result.data

    async def check_condition_with_tool(
        self, tool_name: str, tool_params: Dict[str, Any], deps: AgentDepsT = None
    ) -> Any:
        """Check a condition by calling a desire-phase tool.

        Args:
            tool_name: Name of the desire tool to call
            tool_params: Parameters to pass to the tool
            deps: Optional dependencies to pass to the tool

        Returns:
            The result of the tool call
        """
        return await self.call_tool(tool_name, tool_params, phase="desire", deps=deps)

    async def execute_action_with_tool(
        self, tool_name: str, tool_params: Dict[str, Any], deps: AgentDepsT = None
    ) -> Any:
        """Execute an action by calling an intention-phase tool.

        Args:
            tool_name: Name of the intention tool to call
            tool_params: Parameters to pass to the tool
            deps: Optional dependencies to pass to the tool

        Returns:
            The result of the tool call
        """
        return await self.call_tool(
            tool_name, tool_params, phase="intention", deps=deps
        )

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

        # First check if this intention has structured steps with explicit tool calls
        if intention.steps:
            # Check if there are steps to execute
            while intention.current_step < len(intention.steps):
                current_step = intention.steps[intention.current_step]
                print(
                    f"{bcolors.INTENTION}Executing structured step: {current_step.description}{bcolors.ENDC}"
                )

                # Execute the step as a tool call or prompt
                if current_step.is_tool_call:
                    print(
                        f"{bcolors.SYSTEM}Calling tool: {current_step.tool_name}{bcolors.ENDC}"
                    )
                    await self.execute_action_with_tool(
                        current_step.tool_name,
                        current_step.tool_params,
                        deps=self.deps,
                    )
                else:
                    # Use the description as a prompt
                    await self.run(current_step.description, deps=self.deps)

                # Increment step counter
                intention.increment_current_step(self.log_states)

                # Check if this was the last step
                if intention.current_step >= len(intention.steps):
                    for desire in self.desires:
                        if desire.id == intention.desire_id:
                            desire.update_status(DesireStatus.ACHIEVED, self.log_states)
                            break

            # Remove completed intention
            self.intentions.popleft()

        self.log_states(["intentions"])

    async def fetch_perceptions(self) -> None:
        """Fetch perceptions from all tools registered for the perception phase.

        This method automatically calls all tools registered for the perception phase
        and combines their results into a perception object.

        Returns:
            A dictionary containing all perceptions gathered from perception tools.
        """
        perception_tools = self.get_phase_tools("perception")

        print(
            f"{bcolors.PERCEPTION}Running perception tools: {perception_tools}{bcolors.ENDC}"
        )

        for tool_name in perception_tools:
            tool = self.tool_configs[tool_name]
            try:
                print(f"{bcolors.PERCEPTION}Running tool: {tool_name}{bcolors.ENDC}")
                tool_result = await self.call_tool(
                    tool_name=tool_name,
                    tool_params={},
                    phase="perception",
                    deps=self.deps,
                    result_type=tool.result_type,
                    prompt_suffix=tool.description,
                )

                await self.update_beliefs(tool_result)

            except Exception as e:
                print(
                    f"{bcolors.FAIL}Error running perception tool {tool_name}: {str(e)}{bcolors.ENDC}"
                )

    async def bdi_cycle(self, initial_perception: Any = None) -> None:
        """Run one BDI reasoning cycle."""
        self.log_states(
            types=["beliefs", "desires", "intentions"],
            message="States before starting BDI cycle",
        )
        print(f"{bcolors.SYSTEM}\nBDI cycle starting...{bcolors.ENDC}")

        # Process perceptions
        if initial_perception:
            # Use provided perception if available
            print(
                f"{bcolors.PERCEPTION}Using provided initial perception{bcolors.ENDC}"
            )
            await self.update_beliefs(initial_perception)
        else:
            # Otherwise, automatically fetch perceptions from all perception tools
            print(
                f"{bcolors.PERCEPTION}Automatically fetching perceptions from tools{bcolors.ENDC}"
            )
            await self.fetch_perceptions()

        # If we have string-based desires but no detailed intentions,
        # use the LLM to generate more specific intentions
        if self.desires and not self.intentions:
            await self.generate_intentions_from_desires()

        # Execute intentions
        await self.execute_intentions()

    def perception_handler(self, func: Callable[[Any, BeliefSet], Awaitable[None]]):
        """Decorator for registering a perception handler.

        Perception handlers process incoming perceptions and update the agent's beliefs accordingly.

        Example:
            @agent.perception_handler
            async def temperature_handler(data: Temperature, beliefs: BeliefSet) -> None:
                beliefs.add(Belief(
                    name="room_temperature",
                    value=data,
                    source="temperature_sensor",
                    timestamp=datetime.now().timestamp(),
                ))
        """
        self.register_perception_handler(func)
        return func

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

    def log_states(
        self,
        types: list[Literal["beliefs", "desires", "intentions"]],
        message: str | None = None,
    ):
        if message:
            print(f"{bcolors.SYSTEM}{message}{bcolors.ENDC}")
        if "beliefs" in types:
            print(f"{bcolors.BELIEF}Beliefs: {self.beliefs.beliefs}{bcolors.ENDC}")
        if "desires" in types:
            print(f"{bcolors.DESIRE}Desires: {self.desires}{bcolors.ENDC}")
        if "intentions" in types:
            print(
                f"{bcolors.INTENTION}Intentions: {list(self.intentions)}{bcolors.ENDC}"
            )
