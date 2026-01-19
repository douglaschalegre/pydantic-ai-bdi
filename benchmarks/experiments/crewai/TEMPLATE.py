"""CrewAI Agent Experiment Template

This template shows how to implement a CrewAI multi-agent system for the benchmark study.
Copy this file to experiment-N.py (where N is your participant number) and
implement your multi-agent logic.

Requirements:
    pip install crewai crewai-tools

The framework boilerplate is provided - you only need to:
1. Define your agent roles
2. Create agents with their goals and backstories
3. Define tasks for your agents
4. Implement your multi-agent collaboration logic
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from typing import Any, Dict, List
from benchmarks.experiments.base_experiment import BaseExperiment

# CrewAI imports (install with: pip install crewai crewai-tools)
try:
    from crewai import Agent, Task, Crew, Process
    from crewai_tools import tool
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    print("Warning: CrewAI not installed. Run: pip install crewai crewai-tools")


class CrewAIExperiment(BaseExperiment):
    """Your CrewAI multi-agent implementation.

    Implement your agent roles and collaboration logic below.
    """

    def __init__(self, experiment_id: str):
        super().__init__(experiment_id=experiment_id, framework="crewai")
        self.agents: List[Agent] = []
        self.crew: Crew = None

    async def setup(self):
        """Setup your CrewAI agents."""
        if not CREWAI_AVAILABLE:
            raise ImportError("CrewAI not installed. Run: pip install crewai crewai-tools")

        # TODO: Define your custom tools if needed
        # Example:
        # @tool("File Reader")
        # def read_file(file_path: str) -> str:
        #     """Read contents of a file."""
        #     with open(file_path, 'r') as f:
        #         return f.read()

        # Define your agents
        self.agents = self.create_agents()

    def create_agents(self) -> List[Agent]:
        """Create your agent team.

        TODO: Define your agents with their roles, goals, and backstories.

        Tips:
        - Think about task decomposition
        - Assign specialized roles
        - Consider agent collaboration patterns
        """
        # Example agents (customize these for your approach):

        # Agent 1: Planner
        planner = Agent(
            role="Task Planner",
            goal="Analyze tasks and create detailed execution plans",
            backstory="""You are an expert at breaking down complex tasks
            into manageable steps. You analyze requirements and create
            clear, actionable plans.""",
            verbose=True,
            # tools=[...],  # Add tools if needed
        )

        # Agent 2: Executor
        executor = Agent(
            role="Task Executor",
            goal="Execute planned steps and achieve task goals",
            backstory="""You are skilled at following plans and executing
            tasks efficiently. You handle implementation details and
            problem-solving.""",
            verbose=True,
            # tools=[...],
        )

        # Agent 3: Reviewer (optional)
        reviewer = Agent(
            role="Quality Reviewer",
            goal="Verify task completion and quality",
            backstory="""You carefully review work to ensure goals are met
            and quality standards are maintained.""",
            verbose=True,
        )

        # TODO: Add more agents as needed for your approach
        # Examples: Researcher, Debugger, Optimizer, etc.

        return [planner, executor, reviewer]

    def create_tasks_for_goal(self, goal: str, context: Dict[str, Any]) -> List[Task]:
        """Create CrewAI tasks for achieving the goal.

        TODO: Define how you break down the goal into agent tasks.

        Args:
            goal: The high-level goal to achieve
            context: Initial context/information

        Returns:
            List of Task objects for your crew
        """
        metric_collector = self.get_metric_collector()

        # TODO: Create tasks for your agents
        # Example task structure:

        tasks = []

        # Task 1: Planning
        planning_task = Task(
            description=f"""Analyze this goal and create an execution plan:

            Goal: {goal}
            Context: {context}

            Create a detailed step-by-step plan to achieve this goal.
            """,
            agent=self.agents[0],  # Planner
            expected_output="A detailed execution plan with clear steps"
        )
        tasks.append(planning_task)
        metric_collector.record_step(success=True)

        # Task 2: Execution
        execution_task = Task(
            description="""Follow the plan created by the planner and execute
            each step to achieve the goal.""",
            agent=self.agents[1],  # Executor
            expected_output="Completed task with results",
            context=[planning_task],  # Depends on planning task
        )
        tasks.append(execution_task)
        metric_collector.record_step(success=True)

        # Task 3: Review (optional)
        review_task = Task(
            description="""Review the executed work and verify that the goal
            was achieved successfully.""",
            agent=self.agents[2],  # Reviewer
            expected_output="Review report with success confirmation",
            context=[execution_task],
        )
        tasks.append(review_task)

        # TODO: Add more tasks as needed
        # Consider:
        # - Research tasks
        # - Debugging tasks
        # - Optimization tasks
        # - Documentation tasks

        return tasks

    async def run_task(self, task_definition: Dict[str, Any]) -> Dict[str, Any]:
        """Run a task using your CrewAI multi-agent system.

        The framework handles metric collection automatically.
        """
        goal = task_definition['goal']
        context = task_definition.get('initial_context', {})

        # Create tasks for this goal
        tasks = self.create_tasks_for_goal(goal, context)

        # Create crew with your agents and tasks
        # TODO: Choose your process type:
        # - Process.sequential: Agents work one after another
        # - Process.hierarchical: Manager coordinates agents
        self.crew = Crew(
            agents=self.agents,
            tasks=tasks,
            process=Process.sequential,  # Or Process.hierarchical
            verbose=True,
        )

        # Execute the crew
        try:
            result = self.crew.kickoff()

            return {
                'success': True,  # TODO: Add success detection logic
                'result': result,
                'final_state': {
                    'agents': len(self.agents),
                    'tasks': len(tasks),
                    'output': str(result),
                },
            }

        except Exception as e:
            return {
                'success': False,
                'result': None,
                'final_state': {'error': str(e)},
            }

    async def teardown(self):
        """Clean up after task execution."""
        pass


# ============================================================================
# Benchmark Runner Integration
# ============================================================================

async def main():
    """Run this experiment standalone for testing."""
    from benchmarks.tasks.simple_tasks import SIMPLE_TASKS

    # Create your experiment
    experiment = CrewAIExperiment(experiment_id="experiment-1")  # Change to your number

    # Run a test task
    task = SIMPLE_TASKS[0]
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
    print(f"  Steps: {metrics.steps_executed}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
