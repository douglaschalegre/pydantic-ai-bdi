from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
import os
from pathlib import Path


MODEL_NAME = "gpt-5.4"
SBENCH_ROOT = Path("/Users/douglas/code/masters/sbench")
COMMAND_TIMEOUT_SECONDS = 180
VERBOSE = True


class RunnerConfigError(RuntimeError):
    """Raised when the requested SBench task cannot be run."""


@dataclass(frozen=True)
class RunConfig:
    task_id: str
    model_name: str = MODEL_NAME
    sbench_root: Path = SBENCH_ROOT
    command_timeout_seconds: int = COMMAND_TIMEOUT_SECONDS
    verbose: bool = VERBOSE


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def parse_config(argv: Sequence[str] | None = None) -> RunConfig:
    parser = argparse.ArgumentParser(
        description="Run the BDI harness against one SBench task folder.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--sbench-root", type=Path, default=SBENCH_ROOT)
    parser.add_argument(
        "--tasks",
        dest="task_id",
        required=True,
        metavar="TASK",
        help="Single SBench task folder name to run.",
    )
    parser.add_argument("--model", default=os.getenv("LITELLM_MODEL", MODEL_NAME))
    parser.add_argument(
        "--command-timeout-seconds",
        type=positive_int,
        default=COMMAND_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--quiet",
        dest="verbose",
        action="store_false",
        default=VERBOSE,
        help="Disable verbose BDI output.",
    )
    args = parser.parse_args(argv)
    return RunConfig(
        task_id=args.task_id,
        model_name=args.model,
        sbench_root=args.sbench_root.expanduser(),
        command_timeout_seconds=args.command_timeout_seconds,
        verbose=args.verbose,
    )


def get_task_path(config: RunConfig) -> Path:
    task_path = config.sbench_root / "tasks" / config.task_id
    task_file = task_path / "task.md"
    if not task_file.is_file():
        raise RunnerConfigError(f"SBench task file not found: {task_file}")
    return task_path
