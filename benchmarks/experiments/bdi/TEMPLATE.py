"""BDI Agent Experiment Template

This template shows how to USE the existing BDI agent for benchmark tasks.
Copy this file to experiment-N.py (where N is your participant number).

IMPORTANT: You DON'T implement the BDI architecture from scratch!
The BDI agent is already provided - you just configure and use it.

See toy.py in the project root for a complete usage example.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from typing import Any, Dict
import asyncio
from pydantic_ai.mcp import MCPServerStdio
from benchmarks.experiments.base_experiment import BaseExperiment
from bdi.agent import BDI
from bdi.schemas.desire_schemas import Desire


class BDIExperiment(BaseExperiment):
    """BDI agent experiment using the provided BDI framework.

    The BDI agent is ALREADY implemented in bdi/agent.py
    Your job is to:
    1. Configure it appropriately for each task
    2. Set up MCP servers for tools (filesystem, git, etc.)
    3. Provide initial desires/intentions (optional)
    4. Let the BDI cycle run and collect metrics

    The BDI framework automatically handles:
    - Belief extraction from observations
    - Deliberation (choosing which desires to pursue)
    - Intention generation (planning steps to achieve desires)
    - Plan execution
    - Plan reconsideration
    - Human-in-the-loop intervention (optional)
    """

    def __init__(self, experiment_id: str):
        super().__init__(experiment_id=experiment_id, framework="bdi")
        self.agent: BDI = None
        self.mcp_servers = []

    async def run_task(self, task_definition: Dict[str, Any]) -> Dict[str, Any]:
        """Run a task using the BDI agent.

        The BDI agent is already implemented - you just configure and use it.

        Args:
            task_definition: Contains:
                - goal: str - What to achieve
                - initial_context: dict - Starting information
                - tools_available: list - Available tool names

        Returns:
            dict with:
                - success: bool
                - result: Any
                - final_state: dict
        """
        metric_collector = self.get_metric_collector()

        # Extract task details
        goal = task_definition['goal']
        initial_context = task_definition.get('initial_context', {})
        tools_available = task_definition.get('tools_available', [])

        # ====================================================================
        # Set up MCP servers for tools
        # ====================================================================
        # MCP (Model Context Protocol) servers provide tools to the agent
        # Common servers: filesystem, git, web browser, database, etc.

        # Example: Filesystem server (for file operations)
        # Provides: read_file, write_file, list_directory, etc.
        repo_path = str(Path(__file__).parent.parent.parent.parent.resolve())
        fs_server = MCPServerStdio(
            "npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", repo_path],
            tool_prefix="fs",  # Tools will be named fs_read_file, fs_write_file, etc.
            timeout=60,
        )

        # Example: Git server (for git operations)
        # Provides: git_status, git_log, git_diff, etc.
        # git_server = MCPServerStdio(
        #     "uvx",
        #     args=["mcp-server-git"],
        #     tool_prefix="git",
        #     timeout=60,
        # )

        # Add servers based on what tools are needed
        self.mcp_servers = [fs_server]

        # TODO: Add other MCP servers as needed:
        # - mcp-server-git: Git operations
        # - mcp-server-brave-search: Web search
        # - mcp-server-postgres: Database access
        # - Custom MCP servers you create

        # ====================================================================
        # Configure the BDI agent
        # ====================================================================
        # You can customize:
        # - Model selection (openai:gpt-4, openai:gpt-3.5-turbo, etc.)
        # - Initial desires (goals to achieve)
        # - Initial intentions (optional plan steps)
        # - MCP servers (tools available)
        # - Verbose output
        # - Human-in-the-loop settings

        self.agent = BDI(
            model="openai:gpt-4",  # TODO: Choose your model
            desires=[goal],  # Start with task goal as a desire
            # intentions=[],  # Optional: Provide initial plan steps
            mcp_servers=self.mcp_servers,  # Provide tools via MCP servers
            verbose=True,  # Set to False to reduce output
            enable_human_in_the_loop=False,  # Set to True for intervention
            # log_file_path="experiment_log.md",  # Optional logging
        )

        # ====================================================================
        # Alternative: Add tools using @tool decorator
        # ====================================================================
        # If you don't want to use MCP servers, you can define tools directly
        # Using MCP servers is recommended for standard tools (files, git, etc.)

        # @self.agent.tool
        # async def custom_tool(ctx, param: str) -> str:
        #     """Description of what this tool does."""
        #     # Your tool implementation
        #     return result

        # ====================================================================
        # Run BDI cycles with MCP servers
        # ====================================================================
        # The agent runs in cycles:
        # 1. Belief revision - update knowledge from observations
        # 2. Deliberation - choose which desires to pursue
        # 3. Intention generation - create plan to achieve desires
        # 4. Execution - execute plan steps using tools
        # 5. Reconsideration - check if plan is still valid
        # 6. Repeat until goals achieved or max cycles

        max_cycles = 50
        final_result = None

        # Run BDI cycles within MCP server context
        async with self.agent.run_mcp_servers():
            for cycle_num in range(max_cycles):
                # Record cycle for metrics
                metric_collector.record_cycle()

                try:
                    # Run one BDI cycle
                    # This executes all the BDI reasoning automatically
                    status = await self.agent.bdi_cycle()

                    # Record step execution
                    metric_collector.record_step(success=True)

                    # Check if agent finished
                    if status in ["stopped", "interrupted"]:
                        # Examine results
                        achieved_desires = [
                            d for d in self.agent.desires
                            if d.status.value == "ACHIEVED"
                        ]

                        success = len(achieved_desires) > 0
                        final_result = {
                            'status': status,
                            'achieved_desires': len(achieved_desires),
                            'total_desires': len(self.agent.desires),
                            'cycles': cycle_num + 1,
                        }
                        break

                except Exception as e:
                    metric_collector.record_step(success=False)
                    print(f"Error in cycle {cycle_num + 1}: {e}")
                    final_result = {'error': str(e)}
                    break

                # Brief pause between cycles
                await asyncio.sleep(0.1)

        # ====================================================================
        # Extract final state
        # ====================================================================
        final_state = {
            'beliefs': {b.name: b.value for b in self.agent.beliefs.beliefs},
            'desires': [
                {
                    'description': d.description,
                    'status': d.status.value,
                    'priority': d.priority,
                }
                for d in self.agent.desires
            ],
            'intentions_count': len(self.agent.intentions),
            'cycles_completed': cycle_num + 1,
        }

        # Determine success based on achieved desires
        success = any(d['status'] == 'ACHIEVED' for d in final_state['desires'])

        return {
            'success': success,
            'result': final_result,
            'final_state': final_state,
        }

    async def teardown(self):
        """Clean up after task execution."""
        # MCP servers are automatically cleaned up when exiting the context
        pass


# ============================================================================
# Standalone Testing
# ============================================================================

async def main():
    """Run this experiment standalone for testing.

    This lets you test your BDI configuration before running the full benchmark.
    """
    from benchmarks.tasks.simple_tasks import SIMPLE_TASKS

    # Create your experiment
    experiment = BDIExperiment(experiment_id="experiment-1")  # Change to your number

    # Run a test task
    task = SIMPLE_TASKS[0]  # Try the first simple task
    task_def = {
        'id': task.id,
        'goal': task.goal,
        'initial_context': task.initial_context,
        'tools_available': task.tools_available,
    }

    print("=" * 80)
    print(f"Testing BDI Agent")
    print("=" * 80)
    print(f"Task: {task.name}")
    print(f"Goal: {task.goal}")
    print(f"Context: {task.initial_context}")
    print("=" * 80)
    print()

    # Run the task
    metrics = await experiment.execute_benchmark(task_def)

    # Show results
    print()
    print("=" * 80)
    print("Results:")
    print("=" * 80)
    print(f"  Success: {metrics.task_success}")
    print(f"  Execution time: {metrics.execution_time_seconds:.2f}s")
    print(f"  Cycles: {metrics.cycles_completed}")
    print(f"  Steps: {metrics.steps_executed}")
    print(f"  Retries: {metrics.retries_attempted}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
