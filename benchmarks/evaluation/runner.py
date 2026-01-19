"""Benchmark runner for executing and evaluating tasks across frameworks."""

import argparse
import asyncio
import json
import time
import subprocess
import platform
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from benchmarks.tasks import (
    TaskDefinition,
    TaskResult,
    BenchmarkRun,
    ALL_TASKS,
    SIMPLE_TASKS,
    MEDIUM_TASKS,
    COMPLEX_TASKS,
    TaskCategory,
)
from benchmarks.tasks.validators import run_validator, VALIDATORS
from benchmarks.metrics.collector import MetricsCollector
from benchmarks.agents.base_agent import BaseAgent
from benchmarks.agents.bdi_agent import BDIBenchmarkAgent
from benchmarks.agents.langgraph_agent import LangGraphAgent
from benchmarks.agents.crewai_agent import CrewAIAgent


# Framework registry
# Compares BDI against LangGraph and CrewAI
FRAMEWORKS = {
    'bdi': BDIBenchmarkAgent,
    'langgraph': LangGraphAgent,
    'crewai': CrewAIAgent,
}


class BenchmarkRunner:
    """Runs benchmark tasks and collects results."""

    def __init__(
        self,
        output_dir: str = "benchmarks/results",
        model_name: str = "openai:gpt-4",
        verbose: bool = False,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name
        self.verbose = verbose

        # Create timestamped run directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = self.output_dir / f"run_{timestamp}"
        self.run_dir.mkdir(parents=True, exist_ok=True)

    async def run_task(
        self,
        agent: BaseAgent,
        task: TaskDefinition,
        run_id: str,
    ) -> TaskResult:
        """Run a single task with an agent."""

        print(f"\n{'='*80}")
        print(f"Running: {task.name} ({task.id})")
        print(f"Framework: {agent.get_framework_name()}")
        print(f"Category: {task.category.value}")
        print(f"{'='*80}\n")

        # Create metrics collector
        metrics = MetricsCollector(
            task_id=task.id,
            framework=agent.get_framework_name(),
            model_name=agent.get_model_name(),
        )

        metrics.start()

        # Setup if needed
        if task.setup_function:
            print(f"Running setup: {task.setup_function}")
            # TODO: Call setup function

        try:
            # Execute task with timeout
            result = await asyncio.wait_for(
                agent.execute_task(
                    goal=task.goal,
                    initial_context=task.initial_context,
                    tools_available=task.tools_available,
                ),
                timeout=task.timeout_seconds,
            )

            # Update metrics from execution result
            metrics.step_count = result.steps_executed
            metrics.cycle_count = result.cycles_completed
            metrics.token_usage_input = result.tokens_used_input
            metrics.token_usage_output = result.tokens_used_output
            metrics.api_call_count = result.api_calls_made

        except asyncio.TimeoutError:
            result = None
            print(f"⏱️  Task timed out after {task.timeout_seconds}s")

        except Exception as e:
            result = None
            print(f"❌ Task failed with error: {e}")
            metrics.record_error(str(e), "execution_error")

        metrics.end()

        # Evaluate success criteria
        success = False
        success_score = 0.0
        criteria_met = []
        criteria_failed = []
        partial_criteria = {}

        if result and result.success:
            total_weight = sum(c.weight for c in task.success_criteria)

            for criterion in task.success_criteria:
                validation_result = run_validator(
                    criterion.validator,
                    execution_log=result.execution_log,
                    final_state=result.final_state,
                    **criterion.validator_params
                )

                if validation_result.success:
                    criteria_met.append(criterion.description)
                    success_score += criterion.weight
                    print(f"✓ {criterion.description}")
                else:
                    criteria_failed.append(criterion.description)
                    print(f"✗ {criterion.description}: {validation_result.message}")

            success_score = success_score / total_weight if total_weight > 0 else 0.0
            success = success_score >= 0.9  # 90% threshold for overall success

        # Teardown if needed
        if task.teardown_function:
            print(f"Running teardown: {task.teardown_function}")
            # TODO: Call teardown function

        # Get git commit
        git_commit = self._get_git_commit()

        # Create task result
        task_result = TaskResult(
            task_id=task.id,
            framework=agent.get_framework_name(),
            run_id=run_id,
            success=success,
            success_score=success_score,
            completion_time_seconds=metrics.get_elapsed_time(),
            error_message=result.error_message if result else "Task execution failed",
            step_count=metrics.step_count,
            cycle_count=metrics.cycle_count,
            retry_count=metrics.retry_count,
            human_intervention_count=metrics.human_intervention_count,
            token_usage_input=metrics.token_usage_input,
            token_usage_output=metrics.token_usage_output,
            api_call_count=metrics.api_call_count,
            estimated_cost_usd=metrics.estimate_cost(),
            criteria_met=criteria_met,
            criteria_failed=criteria_failed,
            partial_criteria=partial_criteria,
            execution_log=result.execution_log if result else "",
            final_state=result.final_state if result else {},
            model_name=self.model_name,
            framework_version="1.0.0",  # TODO: Get actual version
            git_commit=git_commit,
            timestamp=time.time(),
        )

        # Print summary
        print(f"\n{'='*80}")
        print(f"Result: {'✓ SUCCESS' if success else '✗ FAILED'} ({success_score:.0%})")
        print(f"Time: {task_result.completion_time_seconds:.2f}s")
        print(f"Steps: {task_result.step_count}")
        print(f"Tokens: {metrics.get_total_tokens():,}")
        print(f"Cost: ${task_result.estimated_cost_usd:.4f}")
        print(f"{'='*80}\n")

        return task_result

    async def run_framework(
        self,
        framework_name: str,
        tasks: List[TaskDefinition],
        run_id: str,
    ) -> List[TaskResult]:
        """Run all tasks for a specific framework."""

        print(f"\n{'#'*80}")
        print(f"# Starting {framework_name.upper()} benchmark")
        print(f"# Tasks: {len(tasks)}")
        print(f"{'#'*80}\n")

        # Create agent
        agent_class = FRAMEWORKS[framework_name]
        agent = agent_class(
            model_name=self.model_name,
            verbose=self.verbose,
        )

        results = []

        for task in tasks:
            result = await self.run_task(agent, task, run_id)
            results.append(result)

            # Save individual result
            result_file = self.run_dir / f"{framework_name}_{task.id}.json"
            with open(result_file, 'w') as f:
                json.dump(result.dict(), f, indent=2)

        return results

    async def run_benchmark(
        self,
        frameworks: List[str],
        task_category: Optional[str] = None,
        specific_tasks: Optional[List[str]] = None,
    ):
        """Run complete benchmark."""

        run_id = datetime.now().isoformat()

        # Determine which tasks to run
        if specific_tasks:
            tasks = [t for t in ALL_TASKS if t.id in specific_tasks]
        elif task_category:
            category_map = {
                'simple': SIMPLE_TASKS,
                'medium': MEDIUM_TASKS,
                'complex': COMPLEX_TASKS,
            }
            tasks = category_map.get(task_category.lower(), ALL_TASKS)
        else:
            tasks = ALL_TASKS

        print(f"Benchmark Configuration:")
        print(f"  Run ID: {run_id}")
        print(f"  Frameworks: {', '.join(frameworks)}")
        print(f"  Tasks: {len(tasks)} ({', '.join(t.id for t in tasks[:3])}...)")
        print(f"  Model: {self.model_name}")
        print(f"  Output: {self.run_dir}")
        print()

        all_results = []

        for framework_name in frameworks:
            if framework_name not in FRAMEWORKS:
                print(f"⚠️  Unknown framework: {framework_name}")
                continue

            results = await self.run_framework(framework_name, tasks, run_id)
            all_results.extend(results)

        # Create benchmark run summary
        benchmark_run = BenchmarkRun(
            run_id=run_id,
            framework="multiple" if len(frameworks) > 1 else frameworks[0],
            model_name=self.model_name,
            timestamp=time.time(),
            git_commit=self._get_git_commit(),
            task_results=all_results,
            total_tasks=len(all_results),
            successful_tasks=sum(1 for r in all_results if r.success),
            failed_tasks=sum(1 for r in all_results if not r.success),
            average_success_score=sum(r.success_score for r in all_results) / len(all_results) if all_results else 0,
            total_time_seconds=sum(r.completion_time_seconds for r in all_results),
            total_cost_usd=sum(r.estimated_cost_usd for r in all_results),
            python_version=platform.python_version(),
            os_platform=platform.platform(),
        )

        # Save summary
        summary_file = self.run_dir / "benchmark_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(benchmark_run.dict(), f, indent=2)

        # Print final summary
        print(f"\n{'#'*80}")
        print(f"# Benchmark Complete")
        print(f"{'#'*80}")
        print(f"Total tasks: {benchmark_run.total_tasks}")
        print(f"Successful: {benchmark_run.successful_tasks} ({benchmark_run.average_success_score:.0%})")
        print(f"Failed: {benchmark_run.failed_tasks}")
        print(f"Total time: {benchmark_run.total_time_seconds:.2f}s")
        print(f"Total cost: ${benchmark_run.total_cost_usd:.4f}")
        print(f"\nResults saved to: {self.run_dir}")
        print(f"{'#'*80}\n")

        return benchmark_run

    def _get_git_commit(self) -> Optional[str]:
        """Get current git commit hash."""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Run BDI agent benchmarks")

    parser.add_argument(
        '--framework',
        '-f',
        choices=list(FRAMEWORKS.keys()) + ['all'],
        default='bdi',
        help="Framework to benchmark"
    )

    parser.add_argument(
        '--category',
        '-c',
        choices=['simple', 'medium', 'complex'],
        help="Task category to run"
    )

    parser.add_argument(
        '--tasks',
        '-t',
        nargs='+',
        help="Specific task IDs to run"
    )

    parser.add_argument(
        '--model',
        '-m',
        default='openai:gpt-4',
        help="Model to use (default: openai:gpt-4)"
    )

    parser.add_argument(
        '--output',
        '-o',
        default='benchmarks/results',
        help="Output directory"
    )

    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help="Verbose output"
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help="Run all frameworks"
    )

    args = parser.parse_args()

    # Determine frameworks to run
    if args.all:
        frameworks = list(FRAMEWORKS.keys())
    elif args.framework == 'all':
        frameworks = list(FRAMEWORKS.keys())
    else:
        frameworks = [args.framework]

    # Create runner
    runner = BenchmarkRunner(
        output_dir=args.output,
        model_name=args.model,
        verbose=args.verbose,
    )

    # Run benchmark
    await runner.run_benchmark(
        frameworks=frameworks,
        task_category=args.category,
        specific_tasks=args.tasks,
    )


if __name__ == '__main__':
    asyncio.run(main())
