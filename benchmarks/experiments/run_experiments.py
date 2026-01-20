#!/usr/bin/env python3
"""Runner for participant experiments.

This script executes participant-implemented agents across all benchmark tasks
and collects metrics for analysis.

Usage:
    # Run all experiments for participant 1
    python -m benchmarks.experiments.run_experiments --participant 1

    # Run specific framework
    python -m benchmarks.experiments.run_experiments --participant 1 --framework bdi

    # Run specific category
    python -m benchmarks.experiments.run_experiments --participant 1 --category simple
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import importlib.util

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from benchmarks.tasks import (
    ALL_TASKS,
    SIMPLE_TASKS,
    MEDIUM_TASKS,
    COMPLEX_TASKS,
    TaskDefinition,
)


class ExperimentRunner:
    """Runs participant experiments and collects results."""

    def __init__(
        self,
        participant_id: int,
        output_dir: str = "benchmarks/results",
    ):
        self.participant_id = participant_id
        self.output_dir = Path(output_dir)
        self.experiments_dir = Path("benchmarks/experiments")

        # Create participant results directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.participant_dir = (
            self.output_dir / f"participant-{participant_id}_{timestamp}"
        )
        self.participant_dir.mkdir(parents=True, exist_ok=True)

    def load_participant_experiment(self, framework: str):
        """Dynamically load participant's experiment file.

        Args:
            framework: 'bdi', 'langgraph', or 'crewai'

        Returns:
            Experiment class instance
        """
        experiment_file = (
            self.experiments_dir / framework / f"experiment-{self.participant_id}.py"
        )

        if not experiment_file.exists():
            raise FileNotFoundError(
                f"Experiment file not found: {experiment_file}\n"
                f"Please implement your {framework} agent in this file."
            )

        # Load the module dynamically
        spec = importlib.util.spec_from_file_location(
            f"{framework}_experiment_{self.participant_id}", experiment_file
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Get the experiment class (convention: BDIExperiment, LangGraphExperiment, CrewAIExperiment)
        class_names = {
            "bdi": "BDIExperiment",
            "langgraph": "LangGraphExperiment",
            "crewai": "CrewAIExperiment",
        }

        experiment_class = getattr(module, class_names[framework])
        return experiment_class(experiment_id=f"participant-{self.participant_id}")

    async def run_task(
        self,
        experiment,
        task: TaskDefinition,
    ) -> Dict[str, Any]:
        """Run a single task with participant's agent."""

        print(f"\n{'=' * 80}")
        print(f"Task: {task.name} ({task.id})")
        print(f"Category: {task.category.value}")
        print(f"{'=' * 80}\n")

        # Prepare task definition
        task_def = {
            "id": task.id,
            "goal": task.goal,
            "initial_context": task.initial_context,
            "tools_available": task.tools_available,
        }

        try:
            # Execute task without timeout - let agent run to natural completion
            # This is important for research to capture full agent behavior
            metrics = await experiment.execute_benchmark(task_def)

            # Validate success criteria
            # Note: We'd need access to execution result for full validation
            # For now, we trust the experiment's success flag

            print("\n✓ Task completed")
            print(f"  Success: {metrics.task_success}")
            print(f"  Time: {metrics.execution_time_seconds:.2f}s")
            print(f"  Steps: {metrics.steps_executed}")
            print(f"  Cycles: {metrics.cycles_completed}")

            return {
                "task_id": task.id,
                "success": metrics.task_success,
                "metrics": metrics.to_dict(),
            }

        except Exception as e:
            print(f"\n❌ Task failed with error: {e}")
            # Even on error, try to return partial metrics if available
            result = {
                "task_id": task.id,
                "success": False,
                "error": str(e),
            }

            # Try to get partial metrics from the experiment
            if hasattr(experiment, "metrics") and experiment.metrics:
                result["partial_metrics"] = experiment.metrics.to_dict()
                print("  Captured partial metrics before failure")

            return result

    async def run_framework(
        self,
        framework: str,
        tasks: List[TaskDefinition],
    ) -> Dict[str, Any]:
        """Run all tasks for a specific framework."""

        print(f"\n{'#' * 80}")
        print(f"# Framework: {framework.upper()}")
        print(f"# Participant: {self.participant_id}")
        print(f"# Tasks: {len(tasks)}")
        print(f"{'#' * 80}\n")

        # Load participant's experiment
        try:
            experiment = self.load_participant_experiment(framework)
        except Exception as e:
            print(f"❌ Failed to load experiment: {e}")
            return {
                "framework": framework,
                "participant_id": self.participant_id,
                "error": str(e),
                "tasks": [],
            }

        # Run all tasks
        results = []
        for task in tasks:
            result = await self.run_task(experiment, task)
            results.append(result)

            # Save individual result
            result_file = self.participant_dir / f"{framework}_{task.id}.json"
            with open(result_file, "w") as f:
                json.dump(result, f, indent=2)

        # Calculate summary statistics
        successful = sum(1 for r in results if r.get("success", False))
        total_time = sum(
            r.get("metrics", {}).get("execution_time_seconds", 0) for r in results
        )

        summary = {
            "framework": framework,
            "participant_id": self.participant_id,
            "total_tasks": len(results),
            "successful_tasks": successful,
            "failed_tasks": len(results) - successful,
            "success_rate": successful / len(results) if results else 0,
            "total_time_seconds": total_time,
            "tasks": results,
        }

        # Save framework summary
        summary_file = self.participant_dir / f"{framework}_summary.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)

        print(f"\n{'#' * 80}")
        print(f"# {framework.upper()} Complete")
        print(
            f"# Success rate: {successful}/{len(results)} ({summary['success_rate']:.0%})"
        )
        print(f"# Total time: {total_time:.2f}s")
        print(f"{'#' * 80}\n")

        return summary

    async def run_all_frameworks(
        self,
        frameworks: List[str],
        task_category: str = None,
    ):
        """Run experiments across all frameworks."""

        # Determine which tasks to run
        if task_category:
            category_map = {
                "simple": SIMPLE_TASKS,
                "medium": MEDIUM_TASKS,
                "complex": COMPLEX_TASKS,
            }
            tasks = category_map.get(task_category.lower(), ALL_TASKS)
        else:
            tasks = ALL_TASKS

        print("Experiment Configuration:")
        print(f"  Participant: {self.participant_id}")
        print(f"  Frameworks: {', '.join(frameworks)}")
        print(f"  Tasks: {len(tasks)}")
        print(f"  Category: {task_category or 'all'}")
        print(f"  Output: {self.participant_dir}")
        print()

        all_results = {}

        for framework in frameworks:
            summary = await self.run_framework(framework, tasks)
            all_results[framework] = summary

        # Save combined results
        combined_file = self.participant_dir / "all_frameworks_summary.json"
        with open(combined_file, "w") as f:
            json.dump(all_results, f, indent=2)

        # Print final summary
        print(f"\n{'#' * 80}")
        print("# All Experiments Complete")
        print(f"{'#' * 80}")
        print(f"Participant: {self.participant_id}")
        print()
        for framework, results in all_results.items():
            print(f"{framework.upper()}:")
            print(f"  Success rate: {results.get('success_rate', 0):.0%}")
            print(f"  Time: {results.get('total_time_seconds', 0):.2f}s")
        print()
        print(f"Results saved to: {self.participant_dir}")
        print(f"{'#' * 80}\n")


async def main():
    parser = argparse.ArgumentParser(description="Run participant experiments")

    parser.add_argument(
        "--participant",
        "-p",
        type=int,
        required=True,
        help="Participant number (e.g., 1, 2, 3)",
    )

    parser.add_argument(
        "--framework",
        "-f",
        choices=["bdi", "langgraph", "crewai", "all"],
        default="all",
        help="Framework to run (default: all)",
    )

    parser.add_argument(
        "--category",
        "-c",
        choices=["simple", "medium", "complex"],
        help="Task category to run (default: all)",
    )

    parser.add_argument(
        "--output",
        "-o",
        default="benchmarks/results",
        help="Output directory (default: benchmarks/results)",
    )

    args = parser.parse_args()

    # Determine frameworks to run
    if args.framework == "all":
        frameworks = ["bdi", "langgraph", "crewai"]
    else:
        frameworks = [args.framework]

    # Create runner
    runner = ExperimentRunner(
        participant_id=args.participant,
        output_dir=args.output,
    )

    # Run experiments
    await runner.run_all_frameworks(
        frameworks=frameworks,
        task_category=args.category,
    )


if __name__ == "__main__":
    asyncio.run(main())
