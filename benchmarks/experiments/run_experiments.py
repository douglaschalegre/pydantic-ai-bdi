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
import importlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from benchmarks.tasks import ALL_TASKS

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))


RUNNER_MODULES = {
    "bdi": "benchmarks.experiments.bdi.runner",
    "langgraph": "benchmarks.experiments.langgraph.runner",
    "crewai": "benchmarks.experiments.crewai.runner",
}


def _load_runner(framework: str):
    module_path = RUNNER_MODULES[framework]
    return importlib.import_module(module_path)


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

        runner = None

        try:
            runner = _load_runner(framework)
            result = await runner.run_experiment(
                participant_path=experiment_path,
                experiment_id=f"participant-{self.participant_id}",
                task_id=task_id,
                participant_id=str(self.participant_id),
            )

            print("\n✓ Task completed")
            print(f"  Success: {result.get('success')}")
            print(f"  Time: {result.get('completion_time_seconds', 0):.2f}s")
            print(f"  Steps: {result.get('step_count', 0)}")
            print(f"  Cycles: {result.get('cycle_count', 0)}")

            return result

        except Exception as exc:
            print(f"\n❌ Task failed with error: {exc}")
            model_name = (
                getattr(runner, "MODEL_NAME", "unknown") if runner else "unknown"
            )
            return {
                "task_id": task_id,
                "framework": framework,
                "run_id": f"participant-{self.participant_id}",
                "success": False,
                "success_score": 0.0,
                "completion_time_seconds": 0.0,
                "error_message": str(exc),
                "step_count": 0,
                "cycle_count": 0,
                "retry_count": 0,
                "human_intervention_count": 0,
                "token_usage_input": None,
                "token_usage_output": None,
                "api_call_count": 0,
                "estimated_cost_usd": 0.0,
                "criteria_met": [],
                "criteria_failed": [],
                "partial_criteria": {},
                "execution_log": "",
                "final_state": {"error": str(exc)},
                "model_name": model_name,
                "framework_version": "unknown",
                "git_commit": None,
                "timestamp": time.time(),
                "lines_of_code": None,
                "functions_defined": None,
                "complexity_score": None,
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

        total_time = result.get("completion_time_seconds", 0)
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
