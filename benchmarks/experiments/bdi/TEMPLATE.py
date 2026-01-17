"""BDI Agent Experiment Template

This template shows how to implement a BDI agent for the benchmark study.
Copy this file to experiment-N.py (where N is your participant number) and
implement the run_task method.

The framework boilerplate is provided - you only need to:
1. Configure the BDI agent
2. Define desires and initial intentions
3. Implement any custom belief extraction or planning logic
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from typing import Any, Dict
from benchmarks.experiments.base_experiment import BaseExperiment, MetricCollector
from bdi.agent import BDI
from bdi.schemas.desire_schemas import Desire
from bdi.schemas.belief_schemas import Belief


class BDIExperiment(BaseExperiment):
    """Your BDI agent implementation.

    Implement your agent logic in the run_task method below.
    """

    def __init__(self, experiment_id: str):
        super().__init__(experiment_id=experiment_id, framework="bdi")
        self.agent: BDI = None

    async def setup(self):
        """Setup your BDI agent.

        The boilerplate for creating a BDI agent is provided.
        Customize as needed for your design.
        """
        # Create BDI agent with your chosen configuration
        self.agent = BDI(
            model="openai:gpt-4",  # Or your preferred model
            verbose=True,  # Set to False to reduce output
            enable_human_in_the_loop=False,  # Enable if you want HITL
        )

        # TODO: Add any custom tools your agent needs
        # Example:
        # @self.agent.tool
        # async def my_custom_tool(ctx, param: str) -> str:
        #     """My custom tool description."""
        #     # Your tool implementation
        #     return result

    async def run_task(self, task_definition: Dict[str, Any]) -> Dict[str, Any]:
        """Implement your BDI agent logic here.

        This is where you implement your approach to solving tasks using BDI.

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

        # TODO: Implement your BDI agent logic
        # Below is a basic example - customize this for your approach

        # 1. Extract goal and context
        goal = task_definition['goal']
        initial_context = task_definition.get('initial_context', {})

        # 2. Add initial beliefs from context
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

        # 3. Create desire(s) for the task
        desire = Desire(
            id=f"task_{task_definition.get('id', 'unknown')}",
            description=goal,
            priority=1.0,
        )
        self.agent.desires.append(desire)

        # 4. Run BDI cycles until task complete or max cycles reached
        max_cycles = 50
        result = None

        for cycle_num in range(max_cycles):
            # Record cycle for metrics
            metric_collector.record_cycle()

            # TODO: Implement your BDI cycle logic
            # This is where you customize the BDI reasoning cycle
            # Options:
            # a) Use the built-in cycle from bdi/cycle.py
            # b) Implement your own cycle logic
            # c) Hybrid approach

            # Example: Check if desire is achieved
            if desire.status.value == "ACHIEVED":
                result = {"achieved": True, "desire": desire.description}
                break

            if desire.status.value == "FAILED":
                result = {"achieved": False, "error": "Task failed"}
                break

            # Record step execution
            metric_collector.record_step(success=True)

            # TODO: Add your step execution logic here
            # ...

        # 5. Extract final state
        final_state = {
            'beliefs': {b.name: b.value for b in self.agent.beliefs.beliefs},
            'desires': [{'id': d.id, 'status': d.status.value} for d in self.agent.desires],
            'cycles': cycle_num + 1,
        }

        return {
            'success': desire.status.value == "ACHIEVED",
            'result': result,
            'final_state': final_state,
        }

    async def teardown(self):
        """Clean up after task execution."""
        # Add any cleanup logic here
        pass


# ============================================================================
# Benchmark Runner Integration
# ============================================================================

async def main():
    """Run this experiment standalone for testing."""
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

    print(f"Running task: {task.name}")
    metrics = await experiment.execute_benchmark(task_def)

    print(f"\nResults:")
    print(f"  Success: {metrics.task_success}")
    print(f"  Execution time: {metrics.execution_time_seconds:.2f}s")
    print(f"  Cycles: {metrics.cycles_completed}")
    print(f"  Steps: {metrics.steps_executed}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
