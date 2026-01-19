"""Base experiment framework for metric collection.

This module provides decorators and base classes that automatically collect
metrics from participant-implemented agents across all frameworks.
"""

import time
import functools
import asyncio
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
import inspect


@dataclass
class ExperimentMetrics:
    """Automatically collected metrics from experiment execution."""

    # Participant info
    experiment_id: str
    framework: str
    participant_id: Optional[str] = None

    # Performance metrics
    start_time: float = 0.0
    end_time: float = 0.0
    execution_time_seconds: float = 0.0

    # Agent metrics (collected automatically)
    steps_executed: int = 0
    cycles_completed: int = 0
    retries_attempted: int = 0

    # LLM metrics (if accessible)
    total_tokens_input: int = 0
    total_tokens_output: int = 0
    llm_calls_made: int = 0

    # Task metrics
    task_id: str = ""
    task_success: bool = False

    # Code metrics (measured from participant's code)
    lines_of_code: int = 0
    functions_defined: int = 0
    complexity_score: float = 0.0

    # Events log
    events: List[Dict[str, Any]] = field(default_factory=list)

    def log_event(self, event_type: str, details: Dict[str, Any]):
        """Log an event during execution."""
        self.events.append({
            'timestamp': time.time(),
            'type': event_type,
            'details': details
        })

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'experiment_id': self.experiment_id,
            'framework': self.framework,
            'participant_id': self.participant_id,
            'execution_time_seconds': self.execution_time_seconds,
            'steps_executed': self.steps_executed,
            'cycles_completed': self.cycles_completed,
            'retries_attempted': self.retries_attempted,
            'total_tokens_input': self.total_tokens_input,
            'total_tokens_output': self.total_tokens_output,
            'llm_calls_made': self.llm_calls_made,
            'task_id': self.task_id,
            'task_success': self.task_success,
            'lines_of_code': self.lines_of_code,
            'functions_defined': self.functions_defined,
            'complexity_score': self.complexity_score,
            'events': self.events,
        }


class MetricCollector:
    """Context manager for automatic metric collection."""

    def __init__(self, metrics: ExperimentMetrics):
        self.metrics = metrics

    def __enter__(self):
        self.metrics.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.metrics.end_time = time.time()
        self.metrics.execution_time_seconds = self.metrics.end_time - self.metrics.start_time
        return False

    def record_step(self, success: bool = True):
        """Record a step execution."""
        self.metrics.steps_executed += 1
        if not success:
            self.metrics.retries_attempted += 1

    def record_cycle(self):
        """Record a BDI cycle (BDI-specific)."""
        self.metrics.cycles_completed += 1

    def record_llm_call(self, tokens_in: int, tokens_out: int):
        """Record an LLM API call."""
        self.metrics.llm_calls_made += 1
        self.metrics.total_tokens_input += tokens_in
        self.metrics.total_tokens_output += tokens_out


def collect_metrics(framework: str, experiment_id: str):
    """Decorator to automatically collect metrics from agent execution.

    Usage:
        @collect_metrics(framework="bdi", experiment_id="experiment-1")
        async def my_agent(task, context):
            # Your agent implementation
            return result
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Create metrics object
            metrics = ExperimentMetrics(
                experiment_id=experiment_id,
                framework=framework,
            )

            # Measure code complexity
            source = inspect.getsource(func)
            metrics.lines_of_code = len(source.split('\n'))

            # Execute with metric collection
            with MetricCollector(metrics) as collector:
                try:
                    # Inject metric collector into kwargs if function accepts it
                    sig = inspect.signature(func)
                    if 'metrics' in sig.parameters:
                        kwargs['metrics'] = collector

                    result = await func(*args, **kwargs)

                    # Mark as successful if no exception
                    metrics.task_success = True

                    return result, metrics

                except Exception as e:
                    metrics.task_success = False
                    metrics.log_event('error', {'message': str(e)})
                    raise

        return wrapper
    return decorator


class BaseExperiment:
    """Base class for participant experiments.

    Participants should inherit from this class and implement the
    `create_agent` and `run_task` methods.
    """

    def __init__(self, experiment_id: str, framework: str):
        self.experiment_id = experiment_id
        self.framework = framework
        self.metrics = ExperimentMetrics(
            experiment_id=experiment_id,
            framework=framework,
        )

    def get_metric_collector(self) -> MetricCollector:
        """Get a metric collector for manual metric recording."""
        return MetricCollector(self.metrics)

    async def setup(self):
        """Setup method called before running tasks.

        Override this to set up your agent, tools, etc.
        """
        pass

    async def teardown(self):
        """Teardown method called after running tasks.

        Override this to clean up resources.
        """
        pass

    async def run_task(self, task_definition: Dict[str, Any]) -> Dict[str, Any]:
        """Run a single task.

        This is the main method participants must implement.

        Args:
            task_definition: Dictionary containing:
                - goal: str - The task goal
                - initial_context: dict - Starting context
                - tools_available: list - Available tool names

        Returns:
            Dictionary containing:
                - success: bool - Whether task succeeded
                - result: Any - Task result/output
                - final_state: dict - Final agent state
        """
        raise NotImplementedError("Participants must implement run_task()")

    async def execute_benchmark(self, task_definition: Dict[str, Any]) -> ExperimentMetrics:
        """Execute a benchmark task with automatic metric collection.

        This method is called by the benchmark runner. Participants don't
        need to override this.
        """
        self.metrics.task_id = task_definition.get('id', 'unknown')

        with MetricCollector(self.metrics) as collector:
            await self.setup()

            try:
                result = await self.run_task(task_definition)
                self.metrics.task_success = result.get('success', False)

            except Exception as e:
                self.metrics.task_success = False
                self.metrics.log_event('error', {'message': str(e)})
                raise

            finally:
                await self.teardown()

        return self.metrics
