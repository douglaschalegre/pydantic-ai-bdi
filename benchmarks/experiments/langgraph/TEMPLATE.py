"""LangGraph Agent Experiment Template

This template shows how to implement a LangGraph agent for the benchmark study.
Copy this file to experiment-N.py (where N is your participant number) and
implement your state machine logic.

Requirements:
    pip install langgraph langchain-openai langchain-core

The framework boilerplate is provided - you only need to:
1. Define your state structure
2. Create nodes for your state machine
3. Define edges and conditional routing
4. Implement your agent logic
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from typing import Any, Dict, TypedDict, Annotated
from benchmarks.experiments.base_experiment import BaseExperiment

# LangGraph imports (install with: pip install langgraph langchain-openai)
try:
    from langgraph.graph import StateGraph, END
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, AIMessage
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    print("Warning: LangGraph not installed. Run: pip install langgraph langchain-openai")


# ============================================================================
# Define Your State Structure
# ============================================================================

class AgentState(TypedDict):
    """Define the state structure for your agent.

    This state is passed between nodes in your graph.
    Customize this based on what information your agent needs to track.
    """
    # Task information
    goal: str
    context: Dict[str, Any]

    # Agent state
    current_step: str
    completed: bool
    success: bool

    # Execution tracking
    steps_taken: int
    results: list

    # TODO: Add your custom state fields here
    # Example: plan: list, observations: dict, etc.


class LangGraphExperiment(BaseExperiment):
    """Your LangGraph agent implementation.

    Implement your state machine logic below.
    """

    def __init__(self, experiment_id: str):
        super().__init__(experiment_id=experiment_id, framework="langgraph")
        self.graph = None
        self.llm = None

    async def setup(self):
        """Setup your LangGraph agent."""
        if not LANGGRAPH_AVAILABLE:
            raise ImportError("LangGraph not installed. Run: pip install langgraph langchain-openai")

        # Initialize LLM
        self.llm = ChatOpenAI(
            model="gpt-4",  # Or your preferred model
            temperature=0,
        )

        # Build your state graph
        self.graph = self.build_graph()

    def build_graph(self) -> StateGraph:
        """Build your state machine graph.

        This is where you define your agent's control flow.

        TODO: Implement your state machine
        - Define nodes (functions that process state)
        - Define edges (transitions between nodes)
        - Add conditional routing if needed
        """
        # Create graph
        workflow = StateGraph(AgentState)

        # TODO: Add your nodes
        # Example:
        workflow.add_node("plan", self.planning_node)
        workflow.add_node("execute", self.execution_node)
        workflow.add_node("evaluate", self.evaluation_node)

        # TODO: Define your edges
        # Example:
        workflow.add_edge("plan", "execute")
        workflow.add_edge("execute", "evaluate")

        # TODO: Add conditional routing
        # Example:
        workflow.add_conditional_edges(
            "evaluate",
            self.should_continue,
            {
                "continue": "plan",
                "end": END,
            }
        )

        # Set entry point
        workflow.set_entry_point("plan")

        return workflow.compile()

    # ========================================================================
    # Define Your Node Functions
    # ========================================================================

    def planning_node(self, state: AgentState) -> AgentState:
        """Planning node: Decide what to do next.

        TODO: Implement your planning logic
        """
        metric_collector = self.get_metric_collector()

        # Example planning logic
        print(f"Planning step {state['steps_taken']}...")

        # TODO: Use LLM to create a plan
        # response = self.llm.invoke([
        #     HumanMessage(content=f"Plan how to: {state['goal']}")
        # ])

        # Update state
        state['current_step'] = "execute"
        metric_collector.record_step(success=True)

        return state

    def execution_node(self, state: AgentState) -> AgentState:
        """Execution node: Execute planned actions.

        TODO: Implement your execution logic
        """
        metric_collector = self.get_metric_collector()

        print(f"Executing step {state['steps_taken']}...")

        # TODO: Execute your actions
        # - Use tools
        # - Update state based on results
        # - Record what happened

        state['steps_taken'] += 1
        metric_collector.record_step(success=True)

        return state

    def evaluation_node(self, state: AgentState) -> AgentState:
        """Evaluation node: Check if task is complete.

        TODO: Implement your evaluation logic
        """
        print("Evaluating progress...")

        # TODO: Check if goal is achieved
        # - Evaluate results
        # - Decide if task is complete
        # - Set success/completion flags

        # Example:
        state['completed'] = state['steps_taken'] >= 10
        state['success'] = True

        return state

    def should_continue(self, state: AgentState) -> str:
        """Conditional routing: Decide next step.

        TODO: Implement your routing logic
        """
        if state['completed']:
            return "end"
        else:
            return "continue"

    # ========================================================================
    # Task Execution
    # ========================================================================

    async def run_task(self, task_definition: Dict[str, Any]) -> Dict[str, Any]:
        """Run a task using your LangGraph agent.

        This method invokes your state machine.
        The framework handles metric collection automatically.
        """
        # Initialize state
        initial_state: AgentState = {
            'goal': task_definition['goal'],
            'context': task_definition.get('initial_context', {}),
            'current_step': 'plan',
            'completed': False,
            'success': False,
            'steps_taken': 0,
            'results': [],
        }

        # Run the graph
        final_state = self.graph.invoke(initial_state)

        return {
            'success': final_state['success'],
            'result': final_state['results'],
            'final_state': final_state,
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
    experiment = LangGraphExperiment(experiment_id="experiment-1")  # Change to your number

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
