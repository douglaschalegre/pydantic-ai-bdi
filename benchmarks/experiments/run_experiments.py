#!/usr/bin/env python3
"""Runner for participant experiments.

This script executes a single task-specific experiment per framework and
collects metrics for analysis.

Usage:
    # Run experiment for participant 1
    python -m benchmarks.experiments.run_experiments --participant 1 --framework bdi --task-id simple_file_read
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from benchmarks.tasks import ALL_TASKS
from benchmarks.experiments.bdi import runner as bdi_runner
from benchmarks.experiments.langgraph import runner as langgraph_runner
from benchmarks.experiments.crewai import runner as crewai_runner


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

    def resolve_experiment_path(self, framework: str, task_id: str) -> Path:
        experiment_file = (
            self.experiments_dir
            / framework
            / task_id
            / f"experiment-{self.participant_id}.py"
        )

        if not experiment_file.exists():
            raise FileNotFoundError(
                f"Experiment file not found: {experiment_file}\n"
                f"Please implement your {framework} agent in this file."
            )

        return experiment_file

    async def run_task(
        self,
        framework: str,
        task_id: str,
    ) -> Dict[str, Any]:
        """Run a single task with participant's agent."""

        task = next((task for task in ALL_TASKS if task.id == task_id), None)
        if task is None:
            raise ValueError(f"Unknown task id: {task_id}")

        print(f"\n{'=' * 80}")
        print(f"Task: {task.name} ({task.id})")
        print(f"Category: {task.category.value}")
        print(f"{'=' * 80}\n")

        experiment_path = self.resolve_experiment_path(framework, task_id)

        runner = {
            "bdi": bdi_runner,
            "langgraph": langgraph_runner,
            "crewai": crewai_runner,
        }[framework]

        try:
            result = await runner.run_experiment(
                participant_path=experiment_path,
                experiment_id=f"participant-{self.participant_id}",
                task_id=task_id,
                participant_id=str(self.participant_id),
            )

            metrics = result.get("metrics", {})
            print("\n✓ Task completed")
            print(f"  Success: {metrics.get('task_success')}")
            print(f"  Time: {metrics.get('execution_time_seconds', 0):.2f}s")
            print(f"  Steps: {metrics.get('steps_executed', 0)}")
            print(f"  Cycles: {metrics.get('cycles_completed', 0)}")

            return {
                "task_id": task_id,
                "task_name": task.name,
                "success": result.get("success", False),
                "metrics": metrics,
                "result": result.get("result"),
            }

        except Exception as exc:
            print(f"\n❌ Task failed with error: {exc}")
            return {
                "task_id": task_id,
                "task_name": task.name,
                "success": False,
                "error": str(exc),
            }

    async def run_framework(
        self,
        framework: str,
        task_id: str,
    ) -> Dict[str, Any]:
        """Run a task-specific experiment for a framework."""

        print(f"\n{'#' * 80}")
        print(f"# Framework: {framework.upper()}")
        print(f"# Participant: {self.participant_id}")
        print(f"# Task: {task_id}")
        print(f"{'#' * 80}\n")

        result = await self.run_task(framework, task_id)

        result_file = self.participant_dir / f"{framework}_{task_id}.json"
        with open(result_file, "w") as f:
            json.dump(result, f, indent=2)

        total_time = result.get("metrics", {}).get("execution_time_seconds", 0)
        summary = {
            "framework": framework,
            "participant_id": self.participant_id,
            "task_id": task_id,
            "success": result.get("success", False),
            "total_time_seconds": total_time,
            "result": result,
        }

        summary_file = self.participant_dir / f"{framework}_summary.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)

        print(f"\n{'#' * 80}")
        print(f"# {framework.upper()} Complete")
        print(f"# Success: {summary['success']}")
        print(f"# Total time: {total_time:.2f}s")
        print(f"{'#' * 80}\n")

        return summary

    async def run_all_frameworks(
        self,
        frameworks: list[str],
        task_id: str,
    ):
        """Run experiments across all frameworks."""

        print("Experiment Configuration:")
        print(f"  Participant: {self.participant_id}")
        print(f"  Frameworks: {', '.join(frameworks)}")
        print(f"  Task: {task_id}")
        print(f"  Output: {self.participant_dir}")
        print()

        all_results = {}

        for framework in frameworks:
            summary = await self.run_framework(framework, task_id)
            all_results[framework] = summary

        combined_file = self.participant_dir / "all_frameworks_summary.json"
        with open(combined_file, "w") as f:
            json.dump(all_results, f, indent=2)

        print(f"\n{'#' * 80}")
        print("# All Experiments Complete")
        print(f"{'#' * 80}")
        print(f"Participant: {self.participant_id}")
        print(f"Task: {task_id}")
        print()
        for framework, results in all_results.items():
            print(f"{framework.upper()}:")
            print(f"  Success: {results.get('success', False)}")
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
        "--task-id",
        required=True,
        help="Task id to run (e.g., simple_file_read)",
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

    await runner.run_all_frameworks(
        frameworks=frameworks,
        task_id=args.task_id,
    )


if __name__ == "__main__":
    asyncio.run(main())
