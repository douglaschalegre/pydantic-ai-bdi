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
    HighLevelIntentionList,
    DetailedStepList,
)

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
        self.initial_intention_guidance: List[str] = intentions or []
        self.perception_handlers: List[Callable[[Any, BeliefSet], Awaitable[None]]] = []
        self.desire_generators: List[
            Callable[[BeliefSet], Awaitable[List[Desire]]]
        ] = []
        self.intention_selectors: List[
            Callable[[List[Desire], BeliefSet], Awaitable[List[Intention]]]
        ] = []
        self.tool_configs: Dict[str, ToolConfig] = {}

        self._initialize_string_desires(desires)

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

    async def generate_intentions_from_desires(self) -> None:
        """Convert desires into detailed, actionable intentions using a two-stage LLM process."""
        if not self.desires:
            print(
                f"{bcolors.SYSTEM}No desires to generate intentions from.{bcolors.ENDC}"
            )
            return
        if self.intentions:
            print(
                f"{bcolors.SYSTEM}Intentions already exist, skipping generation.{bcolors.ENDC}"
            )
            # Optionally: Add logic here if you want to RE-generate intentions even if some exist
            return

        print(
            f"{bcolors.SYSTEM}Starting two-stage intention generation...{bcolors.ENDC}"
        )
        final_intentions: List[Intention] = []

        # --- Context Gathering (Common for both stages) ---
        desires_text = "\n".join(
            [f"- ID: {d.id}, Description: {d.description}" for d in self.desires]
        )
        beliefs_text = (
            "\n".join(
                [
                    f"- {name}: {belief.value}"
                    for name, belief in self.beliefs.beliefs.items()
                ]
            )
            if self.beliefs.beliefs
            else "No current beliefs."
        )
        tools_text = (
            "\n".join(
                [
                    f"- {name}: {config.description}"
                    for name, config in self.tool_configs.items()
                ]
            )
            if self.tool_configs
            else "No tools available."
        )

        # --- Stage 1: Generate High-Level Intentions ---
        # Prepare guidance text if provided
        guidance_section = ""
        if self.initial_intention_guidance:
            guidance_text = "\n".join(
                [f"- {g}" for g in self.initial_intention_guidance]
            )
            guidance_section = f"\n\nUser-Provided Strategic Guidance (Consider these as high-level intentions to guide planning):\n{guidance_text}"

        print(
            f"{bcolors.SYSTEM}Stage 1: Generating high-level intentions...{bcolors.ENDC}"
        )
        prompt_stage1 = f"""
        Given the following overall desires and current beliefs, identify high-level intentions required to fulfill these desires.
        For each relevant desire, propose one or more concise intentions. Each intention should represent a distinct goal or task.
        Focus ONLY on WHAT needs to be done at a high level, not the specific steps yet.

        Overall Desires:
        {desires_text}
        {guidance_section}

        Current Beliefs:
        {beliefs_text}

        Available Tools (for context, but don't plan steps yet):
        {tools_text}

        Respond with a list of high-level intentions using the required format. Associate each intention with its corresponding desire ID.
        """
        try:
            stage1_result = await self.run(
                prompt_stage1, result_type=HighLevelIntentionList
            )
            if (
                not stage1_result
                or not stage1_result.data
                or not stage1_result.data.intentions
            ):
                print(
                    f"{bcolors.FAIL}Stage 1 failed: No high-level intentions generated.{bcolors.ENDC}"
                )
                return
            high_level_intentions = stage1_result.data.intentions
            print(
                f"{bcolors.SYSTEM}Stage 1 successful: Generated {len(high_level_intentions)} high-level intentions.{bcolors.ENDC}"
            )

        except Exception as e:
            print(
                f"{bcolors.FAIL}Stage 1 failed: Error during LLM call: {e}{bcolors.ENDC}"
            )
            return

        # --- Stage 2: Generate Detailed Steps for Each High-Level Intention ---
        print(
            f"{bcolors.SYSTEM}Stage 2: Generating detailed steps for each intention...{bcolors.ENDC}"
        )
        for hl_intention in high_level_intentions:
            print(
                f"{bcolors.INTENTION}  Processing high-level intention for Desire '{hl_intention.desire_id}': {hl_intention.description}{bcolors.ENDC}"
            )

            prompt_stage2 = f"""
            Your task is to create a detailed, step-by-step action plan to achieve the following high-level intention:
            '{hl_intention.description}' (This contributes to overall Desire ID: {hl_intention.desire_id})

            Consider the current beliefs and available tools to formulate the plan.
            Each step in the plan should be a single, concrete action. Steps can be either:
            1. A natural language description of an action for the agent to perform directly.
            2. A specific call to an available tool, including necessary parameters.

            Current Beliefs:
            {beliefs_text}

            Available Tools:
            {tools_text}

            Generate a sequence of detailed steps required to execute this intention. Ensure the steps are logical and sequential.
            Structure the output as a list of steps according to the required format.
            Focus exclusively on HOW to achieve the intention '{hl_intention.description}'.
            """
            try:
                stage2_result = await self.run(
                    prompt_stage2, result_type=DetailedStepList
                )
                if (
                    not stage2_result
                    or not stage2_result.data
                    or not stage2_result.data.steps
                ):
                    print(
                        f"{bcolors.WARNING}  Stage 2 warning: No detailed steps generated for intention '{hl_intention.description}'. Skipping.{bcolors.ENDC}"
                    )
                    continue

                detailed_steps = stage2_result.data.steps
                print(
                    f"{bcolors.SYSTEM}    Generated {len(detailed_steps)} detailed steps.{bcolors.ENDC}"
                )

                # Assemble the final intention
                final_intention = Intention(
                    desire_id=hl_intention.desire_id, steps=detailed_steps
                )
                final_intentions.append(final_intention)

            except Exception as e:
                print(
                    f"{bcolors.FAIL}  Stage 2 failed for intention '{hl_intention.description}': Error during LLM call: {e}{bcolors.ENDC}"
                )
                # Decide if you want to continue with other intentions or stop

        # --- Update Agent State ---
        self.intentions = deque(final_intentions)
        print(
            f"{bcolors.SYSTEM}Intention generation complete. Updated agent with {len(self.intentions)} detailed intentions.{bcolors.ENDC}"
        )
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
