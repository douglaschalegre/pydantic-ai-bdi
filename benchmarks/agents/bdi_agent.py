"""BDI Agent implementation for benchmarking."""

import sys
import os
from pathlib import Path

# Add parent directory to path to import bdi module
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from typing import Any, Dict, List
import asyncio
from benchmarks.agents.base_agent import BaseAgent, AgentExecutionResult, Tool, get_tools_by_names
from benchmarks.metrics.collector import MetricsCollector

from bdi.agent import BDI
from bdi.schemas.desire_schemas import Desire
from bdi.schemas.belief_schemas import Belief


class BDIBenchmarkAgent(BaseAgent):
    """Wrapper for BDI agent to conform to benchmark interface."""

    def __init__(
        self,
        model_name: str = "openai:gpt-4",
        verbose: bool = False,
        timeout_seconds: float = 600.0,
        enable_hitl: bool = False,
    ):
        super().__init__(model_name, verbose, timeout_seconds)
        self.enable_hitl = enable_hitl
        self.agent: Optional[BDI] = None

    async def execute_task(
        self,
        goal: str,
        initial_context: Dict[str, Any],
        tools_available: List[str],
    ) -> AgentExecutionResult:
        """Execute a task using BDI agent."""

        # Create BDI agent
        self.agent = BDI(
            model=self.model_name,
            verbose=self.verbose,
            enable_human_in_the_loop=self.enable_hitl,
        )

        # Register tools
        tools = get_tools_by_names(tools_available)
        self._register_tools_to_bdi(tools)

        # Add initial context as beliefs
        for key, value in initial_context.items():
            self.agent.beliefs.add_belief(
                Belief(
                    name=key,
                    value=value,
                    source="initial_context",
                    timestamp=0.0,
                    certainty=1.0,
                )
            )

        # Create initial desire
        desire = Desire(
            id=f"benchmark_task",
            description=goal,
            priority=1.0,
        )
        self.agent.desires.append(desire)

        # Track metrics
        execution_log = []
        steps_executed = 0
        cycles_completed = 0
        tokens_input = 0
        tokens_output = 0
        api_calls = 0
        success = False
        error_message = None

        try:
            # Execute BDI cycles
            max_cycles = 50
            start_time = asyncio.get_event_loop().time()

            for cycle in range(max_cycles):
                # Check timeout
                if asyncio.get_event_loop().time() - start_time > self.timeout_seconds:
                    error_message = "Task execution timed out"
                    break

                # Run one BDI cycle
                try:
                    # TODO: Integrate with actual BDI cycle and capture metrics
                    # For now, this is a simplified version
                    # In real implementation, you'd call the BDI cycle and track:
                    # - Steps executed
                    # - Token usage from LLM calls
                    # - API calls made

                    cycles_completed += 1

                    # Check if task is complete
                    if desire.status.value in ["ACHIEVED", "FAILED"]:
                        success = desire.status.value == "ACHIEVED"
                        break

                    # For demo purposes, simulate execution
                    execution_log.append(f"Cycle {cycle + 1}: Executing BDI cycle")

                except Exception as e:
                    error_message = str(e)
                    execution_log.append(f"Error in cycle {cycle + 1}: {e}")
                    break

            # Extract final state from beliefs
            final_state = {
                belief.name: belief.value
                for belief in self.agent.beliefs.beliefs
            }

        except Exception as e:
            error_message = str(e)
            execution_log.append(f"Fatal error: {e}")

        return AgentExecutionResult(
            success=success,
            final_state=final_state,
            execution_log="\n".join(execution_log),
            error_message=error_message,
            steps_executed=steps_executed,
            cycles_completed=cycles_completed,
            tokens_used_input=tokens_input,
            tokens_used_output=tokens_output,
            api_calls_made=api_calls,
        )

    def _register_tools_to_bdi(self, tools: List[Tool]):
        """Register tools to BDI agent."""
        for tool in tools:
            # In actual implementation, you'd register tools using
            # the BDI agent's tool registration mechanism
            # This depends on how Pydantic AI handles tools
            pass

    def register_tools(self, tools: List[Tool]):
        """Register tools."""
        self.tools = tools

    def get_framework_name(self) -> str:
        """Get framework name."""
        return "BDI"

    def get_lines_of_code_required(self) -> int:
        """BDI requires moderate setup code."""
        return 40  # Approximate LOC for typical BDI task setup

    def get_complexity_score(self) -> float:
        """BDI has moderate complexity."""
        return 5.5  # BDI concepts (beliefs, desires, intentions) add complexity

    def supports_human_in_the_loop(self) -> bool:
        """BDI supports HITL."""
        return True

    def supports_belief_tracking(self) -> bool:
        """BDI explicitly tracks beliefs."""
        return True

    def supports_plan_reconsideration(self) -> bool:
        """BDI supports plan reconsideration."""
        return True
