"""Benchmark task definitions."""

from .task_schema import (
    TaskCategory,
    TaskDomain,
    SuccessCriteria,
    TaskDefinition,
    TaskResult,
    BenchmarkRun,
)
from .simple_tasks import SIMPLE_TASKS
from .medium_tasks import MEDIUM_TASKS
from .complex_tasks import COMPLEX_TASKS

# All task definitions
ALL_TASKS = SIMPLE_TASKS + MEDIUM_TASKS + COMPLEX_TASKS

__all__ = [
    "TaskCategory",
    "TaskDomain",
    "SuccessCriteria",
    "TaskDefinition",
    "TaskResult",
    "BenchmarkRun",
    "SIMPLE_TASKS",
    "MEDIUM_TASKS",
    "COMPLEX_TASKS",
    "ALL_TASKS",
]
