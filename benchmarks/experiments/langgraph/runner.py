"""LangGraph experiment runner with fixed configuration."""

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv

from antigravity import AntigravityModel, AntigravityProvider
from benchmarks.experiments.base_experiment import ExperimentMetrics, MetricCollector
from benchmarks.metrics.usage_tracker import UsageTracker
from benchmarks.tasks import TaskResult

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))


MODEL_NAME = "gemini-2.5-flash"


def _repo_root() -> Path:
    return REPO_ROOT


def _load_module(participant_path: Path) -> Any:
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
    lines = content.splitlines()
    metrics.lines_of_code = len(lines)
    metrics.functions_defined = sum(
        1 for line in lines if line.lstrip().startswith("def ")
    )


def _build_task_result(
    *,
    task_id: str,
    run_id: str,
    model_name: str,
    metrics: ExperimentMetrics,
    token_usage_input: Optional[int],
    token_usage_output: Optional[int],
    api_call_count: int,
    result: Any,
    error_message: Optional[str] = None,
) -> Dict[str, Any]:
    safe_result = _safe_json_result(result)
    final_state = {"result": safe_result} if safe_result is not None else {}
    return TaskResult(
        task_id=task_id,
        framework=metrics.framework,
        run_id=run_id,
        success=metrics.task_success,
        success_score=1.0 if metrics.task_success else 0.0,
        completion_time_seconds=metrics.execution_time_seconds,
        error_message=error_message,
        step_count=metrics.steps_executed,
        cycle_count=metrics.cycles_completed,
        retry_count=metrics.retries_attempted,
        human_intervention_count=0,
        token_usage_input=token_usage_input,
        token_usage_output=token_usage_output,
        api_call_count=api_call_count,
        estimated_cost_usd=0.0,
        criteria_met=[],
        criteria_failed=[],
        partial_criteria={},
        execution_log="",
        final_state=final_state,
        model_name=model_name,
        framework_version="unknown",
        git_commit=None,
        timestamp=time.time(),
        lines_of_code=metrics.lines_of_code or None,
        functions_defined=metrics.functions_defined or None,
        complexity_score=metrics.complexity_score if metrics.complexity_score else None,
    ).dict()


async def _default_run_agent(
    agent: Any, metric_collector: MetricCollector
) -> Dict[str, Any]:
    if hasattr(agent, "invoke"):
        result = agent.invoke({})
    elif hasattr(agent, "run"):
        result = agent.run()
    else:
        raise AttributeError("LangGraph agent must expose invoke() or run()")
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

    usage_tracker = UsageTracker()
    provider = AntigravityProvider(usage_tracker=usage_tracker)
    model = AntigravityModel(MODEL_NAME, provider=provider)

    agent = build_agent(model=model)
    if agent is None:
        raise ValueError("build_agent(model) must return a LangGraph graph/agent")

    metrics = ExperimentMetrics(
        experiment_id=experiment_id,
        framework="langgraph",
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

    usage_snapshot = usage_tracker.snapshot()
    return _build_task_result(
        task_id=task_id,
        run_id=experiment_id,
        model_name=MODEL_NAME,
        metrics=metrics,
        token_usage_input=usage_snapshot["input_tokens"],
        token_usage_output=usage_snapshot["output_tokens"],
        api_call_count=usage_snapshot["api_calls"],
        result=result,
    )


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
        metrics = result
        print("\nResults:")
        print(f"  Success: {metrics.get('success')}")
        print(f"  Execution time: {metrics.get('completion_time_seconds', 0):.2f}s")
        print(f"  Steps: {metrics.get('step_count', 0)}")

    asyncio.run(_run())


__all__ = ["run_experiment", "main"]
