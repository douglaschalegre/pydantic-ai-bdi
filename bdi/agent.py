"""Main BDI (Belief-Desire-Intention) agent implementation.

This module contains the main BDI agent class that orchestrates all BDI components:
beliefs, desires, intentions, planning, execution, monitoring, and human-in-the-loop.
"""

from typing import List, Optional, TypeVar, Generic
from collections import deque
from datetime import datetime

from pydantic_ai import Agent
from helper.util import bcolors
from bdi.schemas import BeliefSet, Desire
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
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.beliefs = BeliefSet()
        self.desires: List[Desire] = []
        self.intentions: deque = deque()
        self.initial_intention_guidance: List[str] = intentions or []
        self.verbose = verbose
        self.enable_human_in_the_loop = enable_human_in_the_loop
        self.log_file_path = log_file_path
        self.cycle_count = 0

        # Initialize log file if path is provided
        if self.log_file_path:
            self._initialize_log_file()

        self._initialize_string_desires(desires)

    def _initialize_string_desires(self, desire_strings: List[str]) -> None:
        """Initialize desires from string descriptions.

        Args:
            desire_strings: List of desire description strings
        """
        for i, desire_string in enumerate(desire_strings or []):
            desire_id = f"desire_{i + 1}"
            desire = Desire(
                id=desire_id,
                description=desire_string,
                priority=0.5,
            )
            self.desires.append(desire)
        log_states(self, ["desires"])

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

    # Expose module functions as methods for backward compatibility and convenience
    async def generate_intentions_from_desires(self) -> None:
        """Generate intentions from desires using two-stage LLM process."""
        await generate_intentions_from_desires(self)

    async def execute_intentions(self) -> dict:
        """Execute one step of the current intention."""
        return await execute_intentions(self)

    async def bdi_cycle(self) -> None:
        """Run one BDI reasoning cycle."""
        await bdi_cycle(self)

    def log_states(self, types: list, message: str | None = None):
        """Log agent state to console and file."""
        log_states(self, types, message)


__all__ = ["BDI"]
