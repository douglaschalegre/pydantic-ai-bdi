"""Main BDI (Belief-Desire-Intention) agent implementation.

This module contains the main BDI agent class that orchestrates all BDI components:
beliefs, desires, intentions, planning, execution, monitoring, and human-in-the-loop.
"""

from typing import List, Optional, TypeVar, Generic
from collections import deque
from datetime import datetime

from pydantic_ai import Agent
from helper.util import bcolors
from bdi.schemas import BeliefSet, Desire, generate_desire_id, BeliefExtractionResult
from bdi.logging import log_states
from bdi.planning import generate_intentions_from_desires
from bdi.execution import execute_intentions
from bdi.cycle import bdi_cycle

T = TypeVar("T")


class BDI(Agent, Generic[T]):
    """BDI (Belief-Desire-Intention) agent implementation.

    Extends the Pydantic AI Agent with a BDI architecture.
    Relies on the base Agent's capabilities for tool execution,
    including integration with MCP servers for external tools.
    """

    def __init__(
        self,
        *args,
        desires: List[str] = None,
        intentions: List[str] = None,
        verbose: bool = False,
        enable_human_in_the_loop: bool = False,
        log_file_path: Optional[str] = None,
        output_retries: int = 3,  # Higher default for structured output retries
        **kwargs,
    ):
        # Pass output_retries to the parent Agent class
        super().__init__(*args, output_retries=output_retries, **kwargs)
        self.beliefs = BeliefSet()
        self.desires: List[Desire] = []
        self.intentions: deque = deque()
        self.initial_intention_guidance: List[str] = intentions or []
        self.verbose = verbose
        self.enable_human_in_the_loop = enable_human_in_the_loop
        self.log_file_path = log_file_path
        self.cycle_count = 0

        if self.log_file_path:
            self._initialize_log_file()

        self._initialize_string_desires(desires)

    def _initialize_string_desires(self, desire_strings: List[str]) -> None:
        """Initialize desires from string descriptions.

        Args:
            desire_strings: List of desire description strings
        """
        for desire_string in desire_strings or []:
            desire = Desire(
                id=generate_desire_id(desire_string),
                description=desire_string,
                priority=0.5,
            )
            self.desires.append(desire)
        log_states(self, ["desires"])

    async def extract_beliefs_from_desires(self) -> None:
        """Extract factual information from desire descriptions and add to beliefs.

        This method analyzes desire descriptions to extract concrete facts that should
        be recorded as initial beliefs, avoiding the need to rediscover this information
        during execution.
        """
        if not self.desires:
            return

        desires_text = "\n".join(
            [f"- {d.description}" for d in self.desires]
        )

        belief_extraction_prompt = f"""
        Analyze the following desire descriptions and extract any factual information that should be recorded as beliefs.

        Desire Descriptions:
        {desires_text}

        Extract ONLY concrete, factual information explicitly stated in the desires, such as:
        - File paths or directory paths (e.g., "repository path is /path/to/repo")
        - Names or identifiers (e.g., "the project is called X")
        - URLs or endpoints
        - Specific values or configurations mentioned
        - Any other concrete facts that would be useful context

        Do NOT extract:
        - The goals or objectives themselves (these are desires, not beliefs)
        - Inferred or assumed information not explicitly stated
        - Vague or subjective statements

        Return beliefs with clear, concise names (e.g., 'repo_path', 'project_name', 'target_url').
        Set certainty to 1.0 for explicitly stated facts.
        If no factual information can be extracted, return an empty list.
        """

        try:
            extraction_result = await self.run(
                belief_extraction_prompt, output_type=BeliefExtractionResult
            )

            if (
                extraction_result
                and extraction_result.output
                and extraction_result.output.beliefs
            ):
                for belief in extraction_result.output.beliefs:
                    self.beliefs.update(
                        name=belief.name,
                        value=belief.value,
                        source="desire_description",
                        certainty=belief.certainty,
                    )

                if self.verbose:
                    print(
                        f"{bcolors.BELIEF}Extracted {len(extraction_result.output.beliefs)} belief(s) from desires.{bcolors.ENDC}"
                    )
                    log_states(self, ["beliefs"])

        except Exception as e:
            if self.verbose:
                print(
                    f"{bcolors.WARNING}Could not extract beliefs from desires: {e}{bcolors.ENDC}"
                )

    def _initialize_log_file(self) -> None:
        """Initialize the markdown log file with header information."""
        try:
            with open(self.log_file_path, "w", encoding="utf-8") as f:
                f.write("# BDI Agent Execution Log\n\n")
                f.write(f"**Started:** {datetime.now().isoformat()}\n\n")
                f.write("---\n\n")
            if self.verbose:
                print(
                    f"{bcolors.SYSTEM}Log file initialized at: {self.log_file_path}{bcolors.ENDC}"
                )
        except Exception as e:
            print(
                f"{bcolors.FAIL}Failed to initialize log file at {self.log_file_path}: {e}{bcolors.ENDC}"
            )
            self.log_file_path = None

    async def generate_intentions_from_desires(self) -> None:
        """Generate intentions from desires using two-stage LLM process."""
        await generate_intentions_from_desires(self)

    async def execute_intentions(self) -> dict:
        """Execute one step of the current intention."""
        return await execute_intentions(self)

    async def bdi_cycle(self) -> str:
        """Run one BDI reasoning cycle.

        Returns:
            Status string indicating cycle outcome:
            - "executed": Normal cycle with work done
            - "idle_prompted": Agent was idle, user provided new desire
            - "stopped": User requested to quit
            - "interrupted": Non-interactive mode (EOF) or KeyboardInterrupt
        """
        return await bdi_cycle(self)

    def log_states(self, types: list, message: str | None = None):
        """Log agent state to console and file."""
        log_states(self, types, message)


__all__ = ["BDI"]
