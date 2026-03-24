from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
import tempfile
import shlex
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bdi import BDI
from codex import CodexModel, CodexProvider
from pydantic_ai.mcp import MCPServerStdio


READY_MARKER = "All services are ready!"
DECRYPTION_KEY = "theagentcompany is all you need"
DEFAULT_TASKS_FILE = Path(__file__).with_name("tac-tasks.md")
DEFAULT_LOG_FILE = Path(__file__).with_name("tac_bdi_agent.log")
DEFAULT_STRUCTURED_LOG_DIR = Path(__file__).with_name("tac-structured-logs")
DEFAULT_SCREENSHOT_DIR = Path(__file__).with_name("tac-screenshots")
DEFAULT_STATE_FILE = Path(__file__).with_name("tac-state.json")
UNSET = object()


def _prepend_path_entries(entries: Sequence[str]) -> None:
    existing_parts = os.environ.get("PATH", "").split(os.pathsep)
    normalized_existing = [part for part in existing_parts if part]
    updated_parts = list(normalized_existing)

    for entry in reversed(list(entries)):
        if not entry or not Path(entry).exists():
            continue
        if entry in normalized_existing:
            continue
        updated_parts.insert(0, entry)

    os.environ["PATH"] = os.pathsep.join(updated_parts)


def _resolve_executable(
    env_var: str,
    command_name: str,
    fallback_paths: Sequence[str],
) -> str:
    configured = os.environ.get(env_var)
    if configured:
        return configured

    for candidate in (shutil.which(command_name), *fallback_paths):
        if candidate and Path(candidate).exists():
            return candidate

    return command_name


_prepend_path_entries(("/usr/local/bin", "/opt/homebrew/bin"))

DOCKER_BIN = _resolve_executable(
    "DOCKER_BIN",
    "docker",
    (
        "/usr/local/bin/docker",
        "/Applications/Docker.app/Contents/Resources/bin/docker",
        "/opt/homebrew/bin/docker",
    ),
)
NPX_BIN = _resolve_executable(
    "NPX_BIN",
    "npx",
    (
        "/usr/local/bin/npx",
        "/opt/homebrew/bin/npx",
        "/opt/homebrew/lib/node_modules/npm/bin/npx-cli.js",
    ),
)


@dataclass(frozen=True)
class ManagedTask:
    image: str
    slug: str


@dataclass
class TaskStatus:
    executed: bool = False
    evaluated: bool = False


@dataclass
class BatchState:
    tasks_file: str
    updated_at: str
    current_task: str | None
    current_phase: str | None
    task_statuses: dict[str, TaskStatus]
    last_error: str | None


@dataclass(frozen=True)
class CommandResult:
    cmd: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def output(self) -> str:
        output = self.stdout
        if self.stderr:
            output = f"{output}\n[stderr]\n{self.stderr}" if output else self.stderr
        return output.strip()

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0

    def render(self) -> str:
        output = self.output or "(no output)"
        if self.succeeded:
            return output
        return (
            f"Command failed with exit code {self.returncode}.\n"
            f"Command: {' '.join(self.cmd)}\n"
            f"Output:\n{output}"
        )


@dataclass(frozen=True)
class AgentRunSummary:
    loop_status: str
    desire_status: str | None


@dataclass(frozen=True)
class ManagedTaskOutcome:
    task: ManagedTask
    achieved: bool
    executed: bool = False
    evaluated: bool = False
    error: str | None = None
    desire_status: str | None = None
    failure_phase: str | None = None
    container_preserved: bool = False
    container_running: bool = False
    evaluation_result_path: str | None = None


@dataclass(frozen=True)
class EvaluationOutcome:
    succeeded: bool
    result_path: str | None
    trajectory_path: str | None
    result_json: dict[str, object] | None = None
    error: str | None = None


@dataclass(frozen=True)
class EvaluatorConfig:
    api_key: str
    base_url: str
    model: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _archive_suffix() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _candidate_current_png_paths() -> list[Path]:
    return [Path.cwd() / "current.png", REPO_ROOT / "current.png"]


def _archive_current_png(
    task_slug: str, screenshot_root: Path, label: str
) -> Path | None:
    for source in _candidate_current_png_paths():
        if not source.exists() or not source.is_file():
            continue
        task_dir = screenshot_root / task_slug
        task_dir.mkdir(parents=True, exist_ok=True)
        destination = task_dir / f"{label}.png"
        shutil.copy2(source, destination)
        return destination
    return None


def _write_json_file(path: Path, payload: dict[str, object]) -> None:
    _ensure_parent_dir(path)
    temp_path = path.parent / f"{path.name}.tmp"
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    temp_path.replace(path)


def _dedupe_preserve_order(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _normalize_optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _run_command_result(cmd: Sequence[str], timeout_seconds: int) -> CommandResult:
    normalized_cmd = tuple(str(part) for part in cmd)
    try:
        completed = subprocess.run(
            list(normalized_cmd),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return CommandResult(
            cmd=normalized_cmd,
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )
    except FileNotFoundError:
        return CommandResult(
            cmd=normalized_cmd,
            returncode=127,
            stdout="",
            stderr=f"Command not found: {normalized_cmd[0]}",
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        timeout_message = f"Timed out after {timeout_seconds} seconds."
        stderr = f"{timeout_message}\n{stderr}".strip() if stderr else timeout_message
        return CommandResult(
            cmd=normalized_cmd,
            returncode=124,
            stdout=stdout,
            stderr=stderr,
        )


def _run_command_result_streaming(
    cmd: Sequence[str],
    timeout_seconds: int,
    *,
    line_callback: Callable[[str, str], None] | None = None,
) -> CommandResult:
    normalized_cmd = tuple(str(part) for part in cmd)
    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []

    def _consume_stream(stream, target: list[str], stream_name: str) -> None:
        if stream is None:
            return
        try:
            for chunk in iter(stream.readline, ""):
                target.append(chunk)
                if line_callback is not None:
                    line_callback(stream_name, chunk.rstrip("\r\n"))
        finally:
            stream.close()

    try:
        process = subprocess.Popen(
            list(normalized_cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        return CommandResult(
            cmd=normalized_cmd,
            returncode=127,
            stdout="",
            stderr=f"Command not found: {normalized_cmd[0]}",
        )

    stdout_thread = threading.Thread(
        target=_consume_stream,
        args=(process.stdout, stdout_chunks, "stdout"),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_consume_stream,
        args=(process.stderr, stderr_chunks, "stderr"),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()

    timeout_hit = False
    try:
        returncode = process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timeout_hit = True
        process.kill()
        process.wait()
        returncode = 124
    finally:
        stdout_thread.join()
        stderr_thread.join()

    stdout = "".join(stdout_chunks)
    stderr = "".join(stderr_chunks)

    if timeout_hit:
        timeout_message = f"Timed out after {timeout_seconds} seconds."
        stderr = f"{timeout_message}\n{stderr}".strip() if stderr else timeout_message

    return CommandResult(
        cmd=normalized_cmd,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _run_command(cmd: Sequence[str], timeout_seconds: int) -> str:
    result = _run_command_result(cmd, timeout_seconds=timeout_seconds)
    return result.render()


def _docker_exec(container: str, command: str, timeout_seconds: int = 180) -> str:
    cmd = [DOCKER_BIN, "exec", container, "/bin/bash", "-lc", command]
    return _run_command(cmd, timeout_seconds=timeout_seconds)


def _docker_cp_to_container(
    local_path: Path, container_name: str, container_path: str
) -> CommandResult:
    return _run_command_result(
        [DOCKER_BIN, "cp", str(local_path), f"{container_name}:{container_path}"],
        timeout_seconds=120,
    )


def _docker_cp_from_container(
    container_name: str, container_path: str, local_path: Path
) -> CommandResult:
    _ensure_parent_dir(local_path)
    return _run_command_result(
        [DOCKER_BIN, "cp", f"{container_name}:{container_path}", str(local_path)],
        timeout_seconds=120,
    )


def _build_playwright_server() -> MCPServerStdio:
    return MCPServerStdio(
        NPX_BIN,
        args=["-y", "@playwright/mcp@latest"],
        tool_prefix="playwright",
        timeout=300,
    )


def task_slug_from_image(image: str) -> str:
    task_image = image.strip()
    if not task_image:
        raise ValueError("Task image cannot be empty.")

    slug = task_image.rsplit("/", 1)[-1].split(":", 1)[0]
    if slug.endswith("-image"):
        slug = slug[: -len("-image")]
    slug = slug.strip()
    if not slug:
        raise ValueError(f"Could not derive task slug from image '{image}'.")
    return slug


def load_managed_tasks(tasks_file: Path) -> list[ManagedTask]:
    lines = [
        line.strip()
        for line in tasks_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    tasks = [ManagedTask(image=line, slug=task_slug_from_image(line)) for line in lines]
    slugs = [task.slug for task in tasks]
    duplicate_slugs = {slug for slug in slugs if slugs.count(slug) > 1}
    if duplicate_slugs:
        duplicates = ", ".join(sorted(duplicate_slugs))
        raise RuntimeError(f"Duplicate task slugs found in {tasks_file}: {duplicates}")
    return tasks


def _task_mapping(tasks: Sequence[ManagedTask]) -> dict[str, ManagedTask]:
    return {task.slug: task for task in tasks}


def _empty_task_statuses(known_slugs: Sequence[str]) -> dict[str, TaskStatus]:
    return {slug: TaskStatus() for slug in known_slugs}


def _task_status_lists(
    task_statuses: dict[str, TaskStatus],
    known_slugs: Sequence[str],
) -> tuple[list[str], list[str]]:
    executed_tasks: list[str] = []
    evaluated_tasks: list[str] = []
    for slug in known_slugs:
        status = task_statuses.get(slug)
        if status is None:
            continue
        if status.executed:
            executed_tasks.append(slug)
        if status.executed and status.evaluated:
            evaluated_tasks.append(slug)
    return executed_tasks, evaluated_tasks


def _missing_tasks_from_statuses(
    task_statuses: dict[str, TaskStatus],
    known_slugs: Sequence[str],
    current_task: str | None = None,
) -> list[str]:
    missing_tasks = [
        slug
        for slug in known_slugs
        if not task_statuses.get(slug, TaskStatus()).executed
    ]
    if (
        current_task
        and current_task in known_slugs
        and current_task not in missing_tasks
    ):
        missing_tasks.insert(0, current_task)
    return missing_tasks


def _normalize_task_statuses(
    raw_state: dict[str, object], known_slugs: Sequence[str]
) -> dict[str, TaskStatus]:
    known_slug_set = set(known_slugs)
    task_statuses = _empty_task_statuses(known_slugs)

    raw_task_statuses = raw_state.get("task_statuses")
    if isinstance(raw_task_statuses, dict):
        for slug, raw_status in raw_task_statuses.items():
            slug_text = str(slug)
            if slug_text not in known_slug_set or not isinstance(raw_status, dict):
                continue
            executed = bool(raw_status.get("executed", False))
            evaluated = bool(raw_status.get("evaluated", False)) and executed
            task_statuses[slug_text] = TaskStatus(
                executed=executed,
                evaluated=evaluated,
            )
        return task_statuses

    executed_tasks = [
        slug
        for slug in _dedupe_preserve_order(
            [str(slug) for slug in raw_state.get("executed_tasks", [])]
        )
        if slug in known_slug_set
    ]
    executed_set = set(executed_tasks)
    evaluated_tasks = [
        slug
        for slug in _dedupe_preserve_order(
            [str(slug) for slug in raw_state.get("evaluated_tasks", [])]
        )
        if slug in known_slug_set and slug in executed_set
    ]

    for slug in executed_tasks:
        task_statuses[slug].executed = True
    for slug in evaluated_tasks:
        task_statuses[slug].evaluated = True
    return task_statuses


def load_or_initialize_batch_state(
    *,
    state_file: Path,
    tasks_file: Path,
    tasks: Sequence[ManagedTask],
) -> BatchState:
    known_slugs = [task.slug for task in tasks]
    known_slug_set = set(known_slugs)

    if state_file.exists():
        raw_state = json.loads(state_file.read_text(encoding="utf-8"))
        task_statuses = _normalize_task_statuses(raw_state, known_slugs)
        executed_tasks, _ = _task_status_lists(task_statuses, known_slugs)
        executed_set = set(executed_tasks)
        current_task = _normalize_optional_string(raw_state.get("current_task"))
        if current_task not in known_slug_set or current_task in executed_set:
            current_task = None

        state = BatchState(
            tasks_file=str(tasks_file),
            updated_at=_utc_now_iso(),
            current_task=current_task,
            current_phase=_normalize_optional_string(raw_state.get("current_phase")),
            task_statuses=task_statuses,
            last_error=_normalize_optional_string(raw_state.get("last_error")),
        )
    else:
        state = BatchState(
            tasks_file=str(tasks_file),
            updated_at=_utc_now_iso(),
            current_task=None,
            current_phase=None,
            task_statuses=_empty_task_statuses(known_slugs),
            last_error=None,
        )

    persist_batch_state(state_file, state)
    return state


def persist_batch_state(state_file: Path, state: BatchState) -> None:
    state.updated_at = _utc_now_iso()
    _write_json_file(state_file, asdict(state))


def update_batch_state(
    state: BatchState,
    state_file: Path,
    *,
    current_task: object = UNSET,
    current_phase: object = UNSET,
    task_statuses: object = UNSET,
    last_error: object = UNSET,
) -> None:
    if current_task is not UNSET:
        state.current_task = current_task
    if current_phase is not UNSET:
        state.current_phase = current_phase
    if task_statuses is not UNSET:
        state.task_statuses = dict(task_statuses)
    if last_error is not UNSET:
        state.last_error = last_error
    persist_batch_state(state_file, state)


def _mark_task_status(
    state: BatchState,
    slug: str,
    *,
    executed: bool | None = None,
    evaluated: bool | None = None,
) -> dict[str, TaskStatus]:
    task_statuses = dict(state.task_statuses)
    current = task_statuses.get(slug, TaskStatus())
    next_status = TaskStatus(
        executed=current.executed if executed is None else executed,
        evaluated=current.evaluated if evaluated is None else evaluated,
    )
    if not next_status.executed:
        next_status.evaluated = False
    task_statuses[slug] = next_status
    return task_statuses


def _docker_container_exists(container_name: str) -> bool:
    result = _run_command_result(
        [DOCKER_BIN, "container", "inspect", container_name],
        timeout_seconds=30,
    )
    return result.succeeded


def _docker_container_running(container_name: str) -> bool:
    result = _run_command_result(
        [DOCKER_BIN, "inspect", "--format", "{{.State.Running}}", container_name],
        timeout_seconds=30,
    )
    return result.succeeded and result.output.lower() == "true"


def _stop_container_if_running(container_name: str) -> None:
    if not _docker_container_running(container_name):
        return

    result = _run_command_result(
        [DOCKER_BIN, "stop", container_name], timeout_seconds=90
    )
    if not result.succeeded:
        raise RuntimeError(
            f"Could not stop container '{container_name}'.\n{result.render()}"
        )


def _start_container_if_stopped(container_name: str) -> bool:
    if _docker_container_running(container_name):
        return False

    result = _run_command_result(
        [DOCKER_BIN, "start", container_name], timeout_seconds=90
    )
    if not result.succeeded:
        raise RuntimeError(
            f"Could not start container '{container_name}'.\n{result.render()}"
        )
    return True


def _stop_other_task_containers(
    tasks: Sequence[ManagedTask], current_slug: str
) -> None:
    for task in tasks:
        if task.slug == current_slug:
            continue
        if _docker_container_running(task.slug):
            _stop_container_if_running(task.slug)


def _archive_existing_container(container_name: str) -> str | None:
    if not _docker_container_exists(container_name):
        return None

    _stop_container_if_running(container_name)
    archived_name = f"{container_name}--prev-{_archive_suffix()}"
    result = _run_command_result(
        [DOCKER_BIN, "rename", container_name, archived_name],
        timeout_seconds=30,
    )
    if not result.succeeded:
        raise RuntimeError(
            f"Could not archive existing container '{container_name}'.\n{result.render()}"
        )
    return archived_name


def _start_managed_container(task: ManagedTask) -> CommandResult:
    return _run_command_result(
        [
            DOCKER_BIN,
            "run",
            "--name",
            task.slug,
            "--network",
            "host",
            "-dit",
            task.image,
            "/bin/bash",
        ],
        timeout_seconds=120,
    )


def _run_init_in_container(
    *,
    container_name: str,
    server_hostname: str,
    evaluator_config: EvaluatorConfig,
    timeout_seconds: int,
    line_callback: Callable[[str, str], None] | None = None,
) -> CommandResult:
    init_command = (
        f"SERVER_HOSTNAME={shlex.quote(server_hostname)} "
        f"LITELLM_API_KEY={shlex.quote(evaluator_config.api_key)} "
        f"LITELLM_BASE_URL={shlex.quote(evaluator_config.base_url)} "
        f"LITELLM_MODEL={shlex.quote(evaluator_config.model)} "
        "bash /utils/init.sh"
    )
    return _run_command_result_streaming(
        [DOCKER_BIN, "exec", container_name, "/bin/bash", "-lc", init_command],
        timeout_seconds=timeout_seconds,
        line_callback=line_callback,
    )


def _task_artifact_dir(root_dir: Path, slug: str) -> Path:
    return root_dir / slug


def _structured_log_path_for_task(structured_log_dir: Path, task: ManagedTask) -> Path:
    return _task_artifact_dir(structured_log_dir, task.slug) / "structured-log.json"


def _default_text_log_path_for_slug(log_root: Path, slug: str) -> Path:
    return _task_artifact_dir(log_root, slug) / "terminal.log"


def _trajectory_path_for_log(structured_log_path: Path) -> Path:
    return structured_log_path.with_suffix(".trajectory.txt")


def _eval_result_path_for_log(structured_log_path: Path) -> Path:
    return structured_log_path.with_suffix(".eval.json")


def _print_phase(task: ManagedTask, phase: str) -> None:
    print(f"[{task.slug}] {phase}")


def _print_prefixed_output(task: ManagedTask, label: str, text: str) -> None:
    if not text:
        return
    for line in text.splitlines():
        print(f"[{task.slug}] {label}{line}")


def _tail_text(text: str, max_lines: int = 40) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return "\n".join(lines)
    return "\n".join(lines[-max_lines:])


def _is_usage_limit_error(text: str | None) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return (
        "usage_limit_reached" in lowered
        or "usage limit has been reached" in lowered
        or "status_code: 429" in lowered
    )


def _serialize_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    except TypeError:
        return str(value)


def serialize_structured_log_to_trajectory(
    structured_log_path: Path, trajectory_path: Path
) -> Path:
    entries = json.loads(structured_log_path.read_text(encoding="utf-8"))
    lines: list[str] = []

    for index, entry in enumerate(entries, start=1):
        lines.append(f"=== EVENT {index} ===")

        user_text = _serialize_value(entry.get("user"))
        if user_text:
            lines.append("[user]")
            lines.append(user_text)

        assistant_text = _serialize_value(entry.get("assistant"))
        if assistant_text:
            lines.append("[assistant]")
            lines.append(assistant_text)

        tool_calls = entry.get("tool_calls") or []
        for call_index, tool_call in enumerate(tool_calls, start=1):
            lines.append(f"[tool_call {call_index}]")
            func_name = _serialize_value(
                tool_call.get("func_name") or tool_call.get("tool_name")
            )
            if func_name:
                lines.append(f"name: {func_name}")
            args_text = _serialize_value(tool_call.get("args"))
            if args_text:
                lines.append("args:")
                lines.append(args_text)
            result_text = _serialize_value(tool_call.get("result"))
            if result_text:
                lines.append("result:")
                lines.append(result_text)

        lines.append("")

    _ensure_parent_dir(trajectory_path)
    trajectory_path.write_text("\n".join(lines), encoding="utf-8")
    return trajectory_path


def _score_from_result_json(
    result_json: dict[str, object],
) -> tuple[float, float] | None:
    final_score = result_json.get("final_score")
    if isinstance(final_score, dict):
        total = final_score.get("total")
        result = final_score.get("result")
        if total is not None and result is not None:
            return float(result), float(total)

    checkpoints = result_json.get("checkpoints")
    if not isinstance(checkpoints, list) or not checkpoints:
        return None

    total_points = 0.0
    earned_points = 0.0
    for checkpoint in checkpoints:
        if not isinstance(checkpoint, dict):
            return None
        total = checkpoint.get("total")
        result = checkpoint.get("result")
        if total is None or result is None:
            return None
        total_points += float(total)
        earned_points += float(result)
    return earned_points, total_points


def run_evaluator_for_task(
    *,
    container_name: str,
    server_hostname: str,
    evaluator_config: EvaluatorConfig,
    structured_log_path: Path | None,
    trajectory_output_path: Path,
    eval_result_output_path: Path,
) -> EvaluationOutcome:
    try:
        if structured_log_path is not None and structured_log_path.exists():
            serialize_structured_log_to_trajectory(
                structured_log_path, trajectory_output_path
            )
        else:
            _ensure_parent_dir(trajectory_output_path)
            trajectory_output_path.write_text("", encoding="utf-8")

        container_trajectory_path = "/tmp/tac_eval_trajectory.txt"
        container_result_path = "/tmp/tac_eval_result.json"

        cp_in_result = _docker_cp_to_container(
            trajectory_output_path,
            container_name,
            container_trajectory_path,
        )
        if not cp_in_result.succeeded:
            return EvaluationOutcome(
                succeeded=False,
                result_path=None,
                trajectory_path=str(trajectory_output_path),
                error=cp_in_result.render(),
            )

        eval_command = (
            f"DECRYPTION_KEY={shlex.quote(DECRYPTION_KEY)} "
            f"SERVER_HOSTNAME={shlex.quote(server_hostname)} "
            f"LITELLM_API_KEY={shlex.quote(evaluator_config.api_key)} "
            f"LITELLM_BASE_URL={shlex.quote(evaluator_config.base_url)} "
            f"LITELLM_MODEL={shlex.quote(evaluator_config.model)} "
            f"python_default /utils/eval.py --trajectory_path {shlex.quote(container_trajectory_path)} "
            f"--result_path {shlex.quote(container_result_path)}"
        )
        eval_result = _run_command_result(
            [DOCKER_BIN, "exec", container_name, "/bin/bash", "-lc", eval_command],
            timeout_seconds=300,
        )
        if not eval_result.succeeded:
            return EvaluationOutcome(
                succeeded=False,
                result_path=None,
                trajectory_path=str(trajectory_output_path),
                error=eval_result.render(),
            )

        cp_out_result = _docker_cp_from_container(
            container_name,
            container_result_path,
            eval_result_output_path,
        )
        if not cp_out_result.succeeded:
            return EvaluationOutcome(
                succeeded=False,
                result_path=None,
                trajectory_path=str(trajectory_output_path),
                error=cp_out_result.render(),
            )

        result_json = json.loads(eval_result_output_path.read_text(encoding="utf-8"))
        return EvaluationOutcome(
            succeeded=True,
            result_path=str(eval_result_output_path),
            trajectory_path=str(trajectory_output_path),
            result_json=result_json,
        )
    except Exception as exc:
        return EvaluationOutcome(
            succeeded=False,
            result_path=None,
            trajectory_path=str(trajectory_output_path),
            error=str(exc),
        )


def _describe_failed_container(task: ManagedTask) -> tuple[bool, bool]:
    if not _docker_container_exists(task.slug):
        return False, False
    return True, _docker_container_running(task.slug)


def _format_startup_failure(
    *,
    task: ManagedTask,
    phase: str,
    error: str,
    container_preserved: bool,
    container_running: bool,
) -> str:
    lines = [f"failed during {phase}"]
    if container_running:
        lines.append(f"container '{task.slug}' is still running for inspection")
    elif container_preserved:
        lines.append(f"container '{task.slug}' was preserved but is not running")
    tail = _tail_text(error.strip(), max_lines=40)
    if tail:
        lines.append("failure details:")
        lines.extend(f"  {line}" for line in tail.splitlines())
    return "\n".join(lines)


def create_agent(
    *,
    container_name: str,
    model_name: str,
    use_codex_provider: bool,
    verbose: bool,
    log_file_path: str | None,
    structured_log_file_path: str | None,
) -> BDI:
    model = model_name
    if use_codex_provider:
        provider = CodexProvider()
        model = CodexModel(model_name, provider=provider)

    mcp_servers: list[MCPServerStdio] = [_build_playwright_server()]

    desire = (
        f"Complete the task described in /instruction/task.md inside docker container '{container_name}'. "
        "Use available tools to inspect instructions, edit files in /workspace, run commands, "
        "and verify results. The rocketchat login is theagentcompany and the password is theagentcompany"
    )

    agent = BDI(
        model=model,
        desires=[desire],
        verbose=verbose,
        enable_human_in_the_loop=False,
        log_file_path=log_file_path,
        structured_log_file_path=structured_log_file_path,
        mcp_servers=mcp_servers,
    )

    @agent.tool_plain
    def run_in_tac(command: str, timeout_seconds: int = 180) -> str:
        """Run any shell command in the TAC task container."""

        return _docker_exec(container_name, command, timeout_seconds=timeout_seconds)

    return agent


async def run_cycles(
    agent: BDI,
    max_cycles: int,
    cycle_sleep_seconds: float,
    cycle_callback: Callable[[int], None] | None = None,
) -> AgentRunSummary:
    loop_status = "max_cycles_reached"
    async with agent.run_mcp_servers():
        for cycle in range(1, max_cycles + 1):
            print(f"\n===== TAC BDI Cycle {cycle}/{max_cycles} =====")
            status = await agent.bdi_cycle()
            if cycle_callback is not None:
                cycle_callback(cycle)
            if status in ["stopped", "interrupted"]:
                loop_status = status
                print(f"Agent cycle ended with status: {status}")
                break

            await asyncio.sleep(cycle_sleep_seconds)

    print("\nRun finished.")
    desire_status = agent.desires[0].status.value if agent.desires else None
    if desire_status is not None:
        print(f"Final desire status: {desire_status}")

    return AgentRunSummary(loop_status=loop_status, desire_status=desire_status)


async def run_managed_task(
    task: ManagedTask,
    *,
    model_name: str,
    use_codex_provider: bool,
    verbose: bool,
    log_file_path: str | None,
    structured_log_file_path: str | None,
    max_cycles: int,
    cycle_sleep_seconds: float,
    server_hostname: str,
    evaluator_config: EvaluatorConfig,
    init_timeout_seconds: int,
    screenshot_dir: Path,
    phase_callback: Callable[[str], None] | None = None,
) -> ManagedTaskOutcome:
    container_started = False
    task_achieved = False
    task_executed = False
    task_evaluated = False
    current_phase: str | None = None

    def emit(phase: str) -> None:
        nonlocal current_phase
        current_phase = phase
        _print_phase(task, phase)
        if phase_callback is not None:
            phase_callback(phase)

    try:
        archived_name = _archive_existing_container(task.slug)
        if archived_name is not None:
            emit(f"archived existing container as {archived_name}")

        emit("starting_container")
        start_result = _start_managed_container(task)
        if not start_result.succeeded:
            return ManagedTaskOutcome(
                task=task,
                achieved=False,
                executed=task_executed,
                evaluated=task_evaluated,
                error=_format_startup_failure(
                    task=task,
                    phase=current_phase or "starting_container",
                    error=start_result.render(),
                    container_preserved=False,
                    container_running=False,
                ),
                failure_phase=current_phase,
            )
        container_started = True

        emit("running_init")
        init_callback = None
        if verbose:
            init_callback = lambda stream_name, line: print(
                f"[{task.slug}][init][{stream_name}] {line}"
            )
        init_result = _run_init_in_container(
            container_name=task.slug,
            server_hostname=server_hostname,
            evaluator_config=evaluator_config,
            timeout_seconds=init_timeout_seconds,
            line_callback=init_callback,
        )
        if not init_result.succeeded:
            container_preserved, container_running = _describe_failed_container(task)
            return ManagedTaskOutcome(
                task=task,
                achieved=False,
                executed=task_executed,
                evaluated=task_evaluated,
                error=_format_startup_failure(
                    task=task,
                    phase=current_phase or "running_init",
                    error=init_result.render(),
                    container_preserved=container_preserved,
                    container_running=container_running,
                ),
                failure_phase=current_phase,
                container_preserved=container_preserved,
                container_running=container_running,
            )
        if READY_MARKER not in init_result.output:
            container_preserved, container_running = _describe_failed_container(task)
            return ManagedTaskOutcome(
                task=task,
                achieved=False,
                executed=task_executed,
                evaluated=task_evaluated,
                error=_format_startup_failure(
                    task=task,
                    phase=current_phase or "running_init",
                    error=(
                        "Init completed without readiness marker "
                        f"'{READY_MARKER}'.\nOutput:\n{init_result.output or '(no output)'}"
                    ),
                    container_preserved=container_preserved,
                    container_running=container_running,
                ),
                failure_phase=current_phase,
                container_preserved=container_preserved,
                container_running=container_running,
            )

        emit("ready")
        emit("running_agent")
        agent = create_agent(
            container_name=task.slug,
            model_name=model_name,
            use_codex_provider=use_codex_provider,
            verbose=verbose,
            log_file_path=log_file_path,
            structured_log_file_path=structured_log_file_path,
        )
        run_summary = await run_cycles(
            agent,
            max_cycles=max_cycles,
            cycle_sleep_seconds=cycle_sleep_seconds,
            cycle_callback=lambda cycle: _archive_current_png(
                task.slug,
                screenshot_dir,
                f"cycle-{cycle:03d}",
            ),
        )
        _archive_current_png(task.slug, screenshot_dir, "final")
        task_executed = True

        emit("running_evaluator")
        structured_log_path = (
            Path(structured_log_file_path) if structured_log_file_path else None
        )
        trajectory_path = (
            structured_log_path.with_suffix(".trajectory.txt")
            if structured_log_path is not None
            else Path(tempfile.gettempdir()) / f"{task.slug}.trajectory.txt"
        )
        eval_result_path = (
            structured_log_path.with_suffix(".eval.json")
            if structured_log_path is not None
            else Path(tempfile.gettempdir()) / f"{task.slug}.eval.json"
        )
        evaluation = run_evaluator_for_task(
            container_name=task.slug,
            server_hostname=server_hostname,
            evaluator_config=evaluator_config,
            structured_log_path=structured_log_path,
            trajectory_output_path=trajectory_path,
            eval_result_output_path=eval_result_path,
        )
        if not evaluation.succeeded:
            container_preserved, container_running = _describe_failed_container(task)
            error_parts = [
                "Task evaluation failed.",
                evaluation.error or "Unknown evaluator failure.",
                f"Final desire status: {run_summary.desire_status or 'unknown'}",
            ]
            return ManagedTaskOutcome(
                task=task,
                achieved=False,
                executed=task_executed,
                evaluated=task_evaluated,
                error="\n".join(error_parts),
                desire_status=run_summary.desire_status,
                failure_phase=current_phase,
                container_preserved=container_preserved,
                container_running=container_running,
                evaluation_result_path=evaluation.result_path,
            )

        score = (
            _score_from_result_json(evaluation.result_json or {})
            if evaluation.result_json is not None
            else None
        )
        task_evaluated = True
        achieved = score is not None and score[0] >= score[1]

        if achieved:
            task_achieved = True
            return ManagedTaskOutcome(
                task=task,
                achieved=True,
                executed=task_executed,
                evaluated=task_evaluated,
                desire_status=run_summary.desire_status,
                evaluation_result_path=evaluation.result_path,
            )

        if score is None:
            error = (
                "Task evaluation completed but result format was missing checkpoints."
            )
        else:
            error = (
                f"Task did not pass evaluator. Score: {score[0]:g}/{score[1]:g}. "
                f"Final desire status: {run_summary.desire_status or 'unknown'}"
            )
        container_preserved, container_running = _describe_failed_container(task)
        return ManagedTaskOutcome(
            task=task,
            achieved=False,
            executed=task_executed,
            evaluated=task_evaluated,
            error=error,
            desire_status=run_summary.desire_status,
            failure_phase=current_phase,
            container_preserved=container_preserved,
            container_running=container_running,
            evaluation_result_path=evaluation.result_path,
        )
    except Exception as exc:
        container_preserved = container_started and _docker_container_exists(task.slug)
        container_running = (
            _docker_container_running(task.slug) if container_preserved else False
        )
        return ManagedTaskOutcome(
            task=task,
            achieved=False,
            executed=task_executed,
            evaluated=task_evaluated,
            error=str(exc),
            failure_phase=current_phase,
            container_preserved=container_preserved,
            container_running=container_running,
        )
    finally:
        if task_achieved and container_started and _docker_container_exists(task.slug):
            _print_phase(task, "stopping_container")
            _stop_container_if_running(task.slug)


def _next_missing_snapshot(
    *,
    tasks: Sequence[ManagedTask],
    state: BatchState,
) -> list[ManagedTask]:
    task_by_slug = _task_mapping(tasks)
    missing_tasks = _missing_tasks_from_statuses(
        state.task_statuses,
        [task.slug for task in tasks],
        state.current_task,
    )
    return [
        task_by_slug[slug]
        for slug in missing_tasks
        if slug in task_by_slug
        and not state.task_statuses.get(slug, TaskStatus()).executed
    ]


def _next_unevaluated_snapshot(
    *,
    tasks: Sequence[ManagedTask],
    state: BatchState,
) -> list[ManagedTask]:
    task_by_slug = _task_mapping(tasks)
    return [
        task_by_slug[slug]
        for slug, status in state.task_statuses.items()
        if slug in task_by_slug and status.executed and not status.evaluated
    ]


def evaluate_existing_task(
    *,
    task: ManagedTask,
    structured_log_dir: Path,
    server_hostname: str,
    evaluator_config: EvaluatorConfig,
) -> EvaluationOutcome:
    structured_log_path = _structured_log_path_for_task(structured_log_dir, task)
    if not structured_log_path.exists():
        return EvaluationOutcome(
            succeeded=False,
            result_path=None,
            trajectory_path=None,
            error=f"Structured log not found: {structured_log_path}",
        )

    if not _docker_container_exists(task.slug):
        return EvaluationOutcome(
            succeeded=False,
            result_path=None,
            trajectory_path=None,
            error=f"Container '{task.slug}' does not exist.",
        )

    started_for_eval = False
    try:
        started_for_eval = _start_container_if_stopped(task.slug)
        return run_evaluator_for_task(
            container_name=task.slug,
            server_hostname=server_hostname,
            evaluator_config=evaluator_config,
            structured_log_path=structured_log_path,
            trajectory_output_path=_trajectory_path_for_log(structured_log_path),
            eval_result_output_path=_eval_result_path_for_log(structured_log_path),
        )
    finally:
        if started_for_eval and _docker_container_exists(task.slug):
            _stop_container_if_running(task.slug)


async def run_batch(args: argparse.Namespace) -> int:
    tasks_file = Path(args.tasks_file)
    tasks = load_managed_tasks(tasks_file)
    task_by_slug = _task_mapping(tasks)
    state_file = Path(args.state_file)
    structured_log_dir = Path(args.structured_log_dir)
    screenshot_dir = Path(args.screenshot_dir)
    structured_log_dir.mkdir(parents=True, exist_ok=True)
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    state = load_or_initialize_batch_state(
        state_file=state_file,
        tasks_file=tasks_file,
        tasks=tasks,
    )

    evaluator_config = EvaluatorConfig(
        api_key=args.eval_api_key,
        base_url=args.eval_base_url,
        model=args.eval_model,
    )

    if args.eval_only:
        if args.eval_task:
            if args.eval_task not in task_by_slug:
                raise RuntimeError(
                    f"Task slug '{args.eval_task}' not found in {tasks_file}."
                )
            if not state.task_statuses.get(args.eval_task, TaskStatus()).executed:
                raise RuntimeError(
                    f"Task slug '{args.eval_task}' is not marked executed, so there is no completed run to evaluate."
                )
            pending_tasks = [task_by_slug[args.eval_task]]
        else:
            pending_tasks = _next_unevaluated_snapshot(tasks=tasks, state=state)
        print(f"Batch state file: {state_file}")
        print(f"Unevaluated completed tasks this pass: {len(pending_tasks)}")

        for index, task in enumerate(pending_tasks, start=1):
            print(f"\n[{index}/{len(pending_tasks)}] Evaluating {task.slug}")
            _stop_other_task_containers(tasks, task.slug)
            update_batch_state(
                state,
                state_file,
                current_task=task.slug,
                current_phase="running_evaluator",
                last_error=None,
            )

            evaluation = evaluate_existing_task(
                task=task,
                structured_log_dir=structured_log_dir,
                server_hostname=args.server_hostname,
                evaluator_config=evaluator_config,
            )
            if evaluation.succeeded:
                task_statuses = _mark_task_status(state, task.slug, evaluated=True)
                update_batch_state(
                    state,
                    state_file,
                    current_task=task.slug,
                    current_phase="evaluated",
                    task_statuses=task_statuses,
                    last_error=None,
                )
                score = (
                    _score_from_result_json(evaluation.result_json or {})
                    if evaluation.result_json is not None
                    else None
                )
                if score is not None:
                    print(f"[{task.slug}] evaluation score: {score[0]:g}/{score[1]:g}")
                continue

            update_batch_state(
                state,
                state_file,
                current_task=task.slug,
                current_phase="evaluation_failed",
                last_error=evaluation.error,
            )
            _print_prefixed_output(task, "", evaluation.error or "Evaluation failed.")

        update_batch_state(
            state,
            state_file,
            current_task=None,
            current_phase="completed",
            last_error=state.last_error,
        )
        executed_tasks, evaluated_tasks = _task_status_lists(
            state.task_statuses, known_slugs=[task.slug for task in tasks]
        )
        print(f"evaluated tasks: {evaluated_tasks}")
        unevaluated = [slug for slug in executed_tasks if slug not in evaluated_tasks]
        print(f"unevaluated executed tasks: {unevaluated}")
        return 0 if not unevaluated else 1

    pending_tasks = _next_missing_snapshot(tasks=tasks, state=state)

    print(f"Batch state file: {state_file}")
    print(f"Pending tasks this pass: {len(pending_tasks)}")

    for index, task in enumerate(pending_tasks, start=1):
        if state.task_statuses.get(task.slug, TaskStatus()).executed:
            continue

        print(f"\n[{index}/{len(pending_tasks)}] Running {task.slug}")
        _stop_other_task_containers(tasks, task.slug)
        update_batch_state(
            state,
            state_file,
            current_task=task.slug,
            current_phase="queued",
            last_error=None,
        )

        try:
            outcome = await run_managed_task(
                task,
                model_name=args.model,
                use_codex_provider=args.provider == "codex",
                verbose=args.verbose,
                log_file_path=None,
                structured_log_file_path=str(
                    _structured_log_path_for_task(structured_log_dir, task)
                ),
                max_cycles=args.max_cycles,
                cycle_sleep_seconds=args.cycle_sleep,
                server_hostname=args.server_hostname,
                evaluator_config=evaluator_config,
                init_timeout_seconds=args.init_timeout,
                screenshot_dir=screenshot_dir,
                phase_callback=lambda phase, task_slug=task.slug: update_batch_state(
                    state,
                    state_file,
                    current_task=task_slug,
                    current_phase=phase,
                    last_error=None,
                ),
            )
        except Exception as exc:
            outcome = ManagedTaskOutcome(task=task, achieved=False, error=str(exc))

        if _is_usage_limit_error(outcome.error):
            _stop_container_if_running(task.slug)
            update_batch_state(
                state,
                state_file,
                current_task=None,
                current_phase="paused_usage_limit",
                last_error=outcome.error,
            )
            _print_prefixed_output(
                task,
                "",
                "Stopped batch run because model usage limit was reached. Current task progress was not recorded.",
            )
            _print_prefixed_output(task, "", outcome.error or "Usage limit reached.")
            return 2

        if outcome.executed or outcome.evaluated:
            task_statuses = _mark_task_status(
                state,
                task.slug,
                executed=outcome.executed,
                evaluated=outcome.evaluated,
            )
            update_batch_state(
                state,
                state_file,
                task_statuses=task_statuses,
            )

        if outcome.achieved:
            update_batch_state(
                state,
                state_file,
                current_task=task.slug,
                current_phase="achieved",
                last_error=None,
            )
            continue

        update_batch_state(
            state,
            state_file,
            current_task=task.slug,
            current_phase="failed",
            last_error=outcome.error,
        )
        _print_prefixed_output(task, "", outcome.error or "Task failed.")

    update_batch_state(
        state,
        state_file,
        current_task=None,
        current_phase="completed",
        last_error=state.last_error
        if _next_missing_snapshot(tasks=tasks, state=state)
        else None,
    )

    executed_tasks, evaluated_tasks = _task_status_lists(
        state.task_statuses, known_slugs=[task.slug for task in tasks]
    )
    missing_tasks = [
        task.slug for task in _next_missing_snapshot(tasks=tasks, state=state)
    ]
    print(f"executed tasks: {executed_tasks}")
    print(f"evaluated tasks: {evaluated_tasks}")
    print(f"missing tasks: {missing_tasks}")
    return 0 if not missing_tasks else 1


async def run_managed_single_task(args: argparse.Namespace) -> int:
    task = ManagedTask(
        image=args.task_image, slug=task_slug_from_image(args.task_image)
    )
    default_log_root = DEFAULT_LOG_FILE.with_suffix("")
    structured_log_path = (
        Path(args.structured_log_file)
        if args.structured_log_file
        else _structured_log_path_for_task(Path(args.structured_log_dir), task)
    )
    log_file_path = (
        _default_text_log_path_for_slug(default_log_root, task.slug)
        if args.log_file == str(DEFAULT_LOG_FILE)
        else Path(args.log_file)
    )
    _ensure_parent_dir(structured_log_path)
    _ensure_parent_dir(log_file_path)

    try:
        outcome = await run_managed_task(
            task,
            model_name=args.model,
            use_codex_provider=args.provider == "codex",
            verbose=args.verbose,
            log_file_path=str(log_file_path),
            structured_log_file_path=str(structured_log_path),
            max_cycles=args.max_cycles,
            cycle_sleep_seconds=args.cycle_sleep,
            server_hostname=args.server_hostname,
            evaluator_config=EvaluatorConfig(
                api_key=args.eval_api_key,
                base_url=args.eval_base_url,
                model=args.eval_model,
            ),
            init_timeout_seconds=args.init_timeout,
            screenshot_dir=Path(args.screenshot_dir),
        )
    except Exception as exc:
        outcome = ManagedTaskOutcome(task=task, achieved=False, error=str(exc))
    if _is_usage_limit_error(outcome.error):
        _stop_container_if_running(task.slug)
        raise RuntimeError(
            "Stopped single-task run because model usage limit was reached. "
            "Current task progress was not recorded.\n"
            f"{outcome.error}"
        )
    if outcome.achieved:
        return 0

    _print_prefixed_output(task, "", outcome.error or "Task failed.")
    return 1


async def run_manual_container(args: argparse.Namespace) -> int:
    if not _docker_container_running(args.container):
        check = _run_command(
            [DOCKER_BIN, "inspect", "--format", "{{.State.Running}}", args.container],
            30,
        )
        raise RuntimeError(
            f"Container '{args.container}' is not running. Start it first, then run this script.\n"
            f"docker inspect output: {check}"
        )

    default_log_root = DEFAULT_LOG_FILE.with_suffix("")
    log_file_path = (
        _default_text_log_path_for_slug(default_log_root, args.container)
        if args.log_file == str(DEFAULT_LOG_FILE)
        else Path(args.log_file)
    )
    structured_log_path = (
        Path(args.structured_log_file)
        if args.structured_log_file
        else _task_artifact_dir(Path(args.structured_log_dir), args.container)
        / "structured-log.json"
    )
    _ensure_parent_dir(log_file_path)
    _ensure_parent_dir(structured_log_path)

    agent = create_agent(
        container_name=args.container,
        model_name=args.model,
        use_codex_provider=args.provider == "codex",
        verbose=args.verbose,
        log_file_path=str(log_file_path),
        structured_log_file_path=str(structured_log_path),
    )

    screenshot_dir = Path(args.screenshot_dir)
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    await run_cycles(
        agent,
        max_cycles=args.max_cycles,
        cycle_sleep_seconds=args.cycle_sleep,
        cycle_callback=lambda cycle: _archive_current_png(
            args.container,
            screenshot_dir,
            f"cycle-{cycle:03d}",
        ),
    )
    _archive_current_png(args.container, screenshot_dir, "final")

    trajectory_path = structured_log_path.with_suffix(".trajectory.txt")
    eval_result_path = structured_log_path.with_suffix(".eval.json")
    evaluation = run_evaluator_for_task(
        container_name=args.container,
        server_hostname=args.server_hostname,
        evaluator_config=EvaluatorConfig(
            api_key=args.eval_api_key,
            base_url=args.eval_base_url,
            model=args.eval_model,
        ),
        structured_log_path=structured_log_path,
        trajectory_output_path=trajectory_path,
        eval_result_output_path=eval_result_path,
    )
    if not evaluation.succeeded:
        raise RuntimeError(
            f"Evaluation failed for container '{args.container}'.\n{evaluation.error}"
        )

    score = (
        _score_from_result_json(evaluation.result_json or {})
        if evaluation.result_json is not None
        else None
    )
    if score is None:
        raise RuntimeError(
            f"Evaluation result for container '{args.container}' did not contain checkpoints."
        )

    print(f"Evaluation result path: {evaluation.result_path}")
    print(f"Trajectory path: {evaluation.trajectory_path}")
    print(f"Evaluation score: {score[0]:g}/{score[1]:g}")
    return 0 if score[0] >= score[1] else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a BDI agent against TAC task containers."
    )
    parser.add_argument(
        "--container",
        default="tac-test",
        help="Docker container name for manual mode (default: tac-test)",
    )
    parser.add_argument("--task-image", default=None, help="Run a managed TAC image")
    parser.add_argument(
        "--tasks-file",
        default=None,
        help="Run all task images from a file with resumable state",
    )
    parser.add_argument(
        "--eval-only",
        action="store_true",
        help="In batch mode, run evaluator only for already executed but unevaluated tasks",
    )
    parser.add_argument(
        "--eval-task",
        default=None,
        help="With --eval-only and --tasks-file, evaluate only the specified executed task slug",
    )
    parser.add_argument("--model", default="gpt-5.3-codex", help="Model name")
    parser.add_argument(
        "--provider",
        choices=["codex", "native"],
        default="codex",
        help="Use Codex OAuth provider or pass model string directly to PydanticAI",
    )
    parser.add_argument(
        "--max-cycles", type=int, default=100, help="Maximum BDI cycles"
    )
    parser.add_argument(
        "--cycle-sleep", type=float, default=1.0, help="Seconds to sleep between cycles"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable verbose BDI logs"
    )
    parser.add_argument(
        "--log-file",
        default=str(DEFAULT_LOG_FILE),
        help="Path for terminal-mirrored BDI logs",
    )
    parser.add_argument(
        "--structured-log-file",
        default=None,
        help="Path for structured JSON BDI run logs in manual/single-task mode",
    )
    parser.add_argument(
        "--structured-log-dir",
        default=str(DEFAULT_STRUCTURED_LOG_DIR),
        help="Directory for per-task structured logs in managed modes",
    )
    parser.add_argument(
        "--screenshot-dir",
        default=str(DEFAULT_SCREENSHOT_DIR),
        help="Directory for per-task archived Playwright screenshots",
    )
    parser.add_argument(
        "--state-file",
        default=str(DEFAULT_STATE_FILE),
        help="Path for resumable batch state/progress JSON",
    )
    parser.add_argument(
        "--server-hostname",
        default="192.168.0.6",
        help="SERVER_HOSTNAME used for /utils/init.sh",
    )
    parser.add_argument(
        "--init-timeout",
        type=int,
        default=600,
        help="Seconds to wait for /utils/init.sh to complete",
    )
    parser.add_argument(
        "--eval-api-key",
        default="sk-1234",
        help="LITELLM_API_KEY passed to TAC init and evaluator",
    )
    parser.add_argument(
        "--eval-base-url",
        default="http://0.0.0.0:4000",
        help="LITELLM_BASE_URL passed to TAC init and evaluator",
    )
    parser.add_argument(
        "--eval-model",
        default="chatgpt/gpt-5.4-mini",
        help="LITELLM_MODEL passed to TAC init and evaluator",
    )

    args = parser.parse_args()

    if args.task_image and args.tasks_file:
        parser.error("Use either --task-image or --tasks-file, not both.")
    if args.tasks_file and args.structured_log_file:
        parser.error(
            "--structured-log-file is only supported for manual or --task-image runs."
        )
    if args.eval_only and not args.tasks_file:
        parser.error("--eval-only requires --tasks-file.")
    if args.eval_task and not args.eval_only:
        parser.error("--eval-task requires --eval-only.")
    return args


async def _main() -> int:
    args = parse_args()

    if args.tasks_file:
        return await run_batch(args)
    if args.task_image:
        return await run_managed_single_task(args)
    return await run_manual_container(args)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
