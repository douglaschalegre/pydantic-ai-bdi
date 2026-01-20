"""CrewAI experiment runner with fixed configuration."""

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

from benchmarks.experiments.base_experiment import ExperimentMetrics, MetricCollector

MODEL_NAME = "gpt-4o-mini"


def _repo_root() -> Path:
    return REPO_ROOT


def _load_module(participant_path: Path):
    spec = importlib.util.spec_from_file_location(
        participant_path.stem,
        participant_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {participant_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parse_participant_id(participant_path: Path) -> Optional[str]:
    stem = participant_path.stem
    if stem.startswith("experiment-"):
        return stem.split("-", 1)[1]
    return None


def _safe_json_result(result: Any) -> Any:
    if result is None:
        return None
    try:
        json.dumps(result)
        return result
    except TypeError:
        return str(result)


def _collect_code_metrics(metrics: ExperimentMetrics, participant_path: Path) -> None:
    try:
        content = participant_path.read_text(encoding="utf-8")
    except Exception:
        return
    metrics.lines_of_code = len(content.splitlines())
    metrics.functions_defined = sum(1 for line in content.splitlines() if line.lstrip().startswith("def "))


async def _default_run_agent(agent: Any, metric_collector: MetricCollector) -> Dict[str, Any]:
    if hasattr(agent, "kickoff"):
        result = agent.kickoff()
    else:
        raise AttributeError("CrewAI agent must expose kickoff()")
    metric_collector.record_step(success=True)
    return {"result": result, "success": True}


async def run_experiment(
    participant_path: Path,
    experiment_id: str,
    task_id: str,
    participant_id: Optional[str] = None,
) -> Dict[str, Any]:
    load_dotenv()
    module = _load_module(participant_path)

    build_agent = getattr(module, "build_agent", None)
    if not callable(build_agent):
        raise AttributeError("Participant file must define build_agent(model)")

    os.environ["OPENAI_MODEL_NAME"] = MODEL_NAME
    model = MODEL_NAME

    agent = build_agent(model=model)
    if agent is None:
        raise ValueError("build_agent(model) must return a CrewAI crew/agent")

    metrics = ExperimentMetrics(
        experiment_id=experiment_id,
        framework="crewai",
        participant_id=participant_id,
    )
    metrics.task_id = task_id
    _collect_code_metrics(metrics, participant_path)

    run_agent = getattr(module, "run_agent", None)
    result: Any = None

    with MetricCollector(metrics) as collector:
        try:
            if callable(run_agent):
                if inspect.iscoroutinefunction(run_agent):
                    result = await run_agent(agent, collector)
                else:
                    result = run_agent(agent, collector)
            else:
                result = await _default_run_agent(agent, collector)
            if isinstance(result, dict) and "success" in result:
                metrics.task_success = bool(result["success"])
            else:
                metrics.task_success = True
        except Exception as exc:
            metrics.task_success = False
            metrics.log_event("error", {"message": str(exc)})
            raise

    return {
        "task_id": task_id,
        "success": metrics.task_success,
        "metrics": metrics.to_dict(),
        "result": _safe_json_result(result),
    }


def main(participant_path: str) -> None:
    path = Path(participant_path).resolve()
    task_id = path.parent.name
    participant_id = _parse_participant_id(path)
    experiment_id = f"participant-{participant_id or 'unknown'}"

    async def _run():
        result = await run_experiment(
            participant_path=path,
            experiment_id=experiment_id,
            task_id=task_id,
            participant_id=participant_id,
        )
        metrics = result.get("metrics", {})
        print("\nResults:")
        print(f"  Success: {metrics.get('task_success')}")
        print(f"  Execution time: {metrics.get('execution_time_seconds', 0):.2f}s")
        print(f"  Steps: {metrics.get('steps_executed', 0)}")

    asyncio.run(_run())


__all__ = ["run_experiment", "main"]
