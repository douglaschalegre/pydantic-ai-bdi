from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bdi import BDI
from codex import CodexModel, CodexProvider
from pydantic_ai.mcp import MCPServerStdio


READY_MARKER = "All services are ready!"
DEFAULT_TASKS_FILE = Path(__file__).with_name("tac-tasks.md")
DEFAULT_LOG_FILE = Path(__file__).with_name("tac_bdi_agent.log")
DEFAULT_STRUCTURED_LOG_DIR = Path(__file__).with_name("tac-structured-logs")
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
class BatchState:
    tasks_file: str
    updated_at: str
    current_task: str | None
    current_phase: str | None
    executed_tasks: list[str]
    missing_tasks: list[str]
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
    error: str | None = None
    desire_status: str | None = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _archive_suffix() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


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


def _run_command(cmd: Sequence[str], timeout_seconds: int) -> str:
    result = _run_command_result(cmd, timeout_seconds=timeout_seconds)
    return result.render()


def _docker_exec(container: str, command: str, timeout_seconds: int = 180) -> str:
    cmd = [DOCKER_BIN, "exec", container, "/bin/bash", "-lc", command]
    return _run_command(cmd, timeout_seconds=timeout_seconds)


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
        executed_tasks = [
            slug
            for slug in _dedupe_preserve_order(
                [str(slug) for slug in raw_state.get("executed_tasks", [])]
            )
            if slug in known_slug_set
        ]
        executed_set = set(executed_tasks)
        missing_tasks = [
            slug
            for slug in _dedupe_preserve_order(
                [str(slug) for slug in raw_state.get("missing_tasks", [])]
            )
            if slug in known_slug_set and slug not in executed_set
        ]
        current_task = _normalize_optional_string(raw_state.get("current_task"))
        if current_task not in known_slug_set or current_task in executed_set:
            current_task = None
        if current_task and current_task not in missing_tasks:
            missing_tasks.insert(0, current_task)

        state = BatchState(
            tasks_file=str(tasks_file),
            updated_at=_utc_now_iso(),
            current_task=current_task,
            current_phase=_normalize_optional_string(raw_state.get("current_phase")),
            executed_tasks=executed_tasks,
            missing_tasks=missing_tasks,
            last_error=_normalize_optional_string(raw_state.get("last_error")),
        )
    else:
        state = BatchState(
            tasks_file=str(tasks_file),
            updated_at=_utc_now_iso(),
            current_task=None,
            current_phase=None,
            executed_tasks=[],
            missing_tasks=list(known_slugs),
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
    executed_tasks: object = UNSET,
    missing_tasks: object = UNSET,
    last_error: object = UNSET,
) -> None:
    if current_task is not UNSET:
        state.current_task = current_task
    if current_phase is not UNSET:
        state.current_phase = current_phase
    if executed_tasks is not UNSET:
        state.executed_tasks = list(executed_tasks)
    if missing_tasks is not UNSET:
        state.missing_tasks = list(missing_tasks)
    if last_error is not UNSET:
        state.last_error = last_error
    persist_batch_state(state_file, state)


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

    result = _run_command_result([DOCKER_BIN, "stop", container_name], timeout_seconds=90)
    if not result.succeeded:
        raise RuntimeError(
            f"Could not stop container '{container_name}'.\n{result.render()}"
        )


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
    timeout_seconds: int,
) -> CommandResult:
    init_command = f"SERVER_HOSTNAME={shlex.quote(server_hostname)} bash /utils/init.sh"
    return _run_command_result(
        [DOCKER_BIN, "exec", container_name, "/bin/bash", "-lc", init_command],
        timeout_seconds=timeout_seconds,
    )


def _structured_log_path_for_task(structured_log_dir: Path, task: ManagedTask) -> Path:
    return structured_log_dir / f"{task.slug}.json"


def _print_phase(task: ManagedTask, phase: str) -> None:
    print(f"[{task.slug}] {phase}")


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
    agent: BDI, max_cycles: int, cycle_sleep_seconds: float
) -> AgentRunSummary:
    loop_status = "max_cycles_reached"
    async with agent.run_mcp_servers():
        for cycle in range(1, max_cycles + 1):
            print(f"\n===== TAC BDI Cycle {cycle}/{max_cycles} =====")
            status = await agent.bdi_cycle()
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
    init_timeout_seconds: int,
    phase_callback: Callable[[str], None] | None = None,
) -> ManagedTaskOutcome:
    container_started = False

    def emit(phase: str) -> None:
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
                task=task, achieved=False, error=start_result.render()
            )
        container_started = True

        emit("running_init")
        init_result = _run_init_in_container(
            container_name=task.slug,
            server_hostname=server_hostname,
            timeout_seconds=init_timeout_seconds,
        )
        if not init_result.succeeded:
            return ManagedTaskOutcome(
                task=task, achieved=False, error=init_result.render()
            )
        if READY_MARKER not in init_result.output:
            return ManagedTaskOutcome(
                task=task,
                achieved=False,
                error=(
                    "Init completed without readiness marker "
                    f"'{READY_MARKER}'.\nOutput:\n{init_result.output or '(no output)'}"
                ),
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
        )

        achieved = run_summary.desire_status == "achieved"
        if achieved:
            return ManagedTaskOutcome(
                task=task,
                achieved=True,
                desire_status=run_summary.desire_status,
            )

        error = (
            f"Task did not reach achieved state. Final desire status: "
            f"{run_summary.desire_status or 'unknown'}"
        )
        return ManagedTaskOutcome(
            task=task,
            achieved=False,
            error=error,
            desire_status=run_summary.desire_status,
        )
    finally:
        if container_started and _docker_container_exists(task.slug):
            _print_phase(task, "stopping_container")
            _stop_container_if_running(task.slug)


def _next_missing_snapshot(
    *,
    tasks: Sequence[ManagedTask],
    state: BatchState,
) -> list[ManagedTask]:
    task_by_slug = _task_mapping(tasks)
    return [
        task_by_slug[slug]
        for slug in state.missing_tasks
        if slug in task_by_slug and slug not in set(state.executed_tasks)
    ]


async def run_batch(args: argparse.Namespace) -> int:
    tasks_file = Path(args.tasks_file)
    tasks = load_managed_tasks(tasks_file)
    state_file = Path(args.state_file)
    structured_log_dir = Path(args.structured_log_dir)
    structured_log_dir.mkdir(parents=True, exist_ok=True)

    state = load_or_initialize_batch_state(
        state_file=state_file,
        tasks_file=tasks_file,
        tasks=tasks,
    )
    pending_tasks = _next_missing_snapshot(tasks=tasks, state=state)

    print(f"Batch state file: {state_file}")
    print(f"Pending tasks this pass: {len(pending_tasks)}")

    for index, task in enumerate(pending_tasks, start=1):
        if task.slug in state.executed_tasks:
            continue

        print(f"\n[{index}/{len(pending_tasks)}] Running {task.slug}")
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
                init_timeout_seconds=args.init_timeout,
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

        if outcome.achieved:
            executed_tasks = list(state.executed_tasks)
            if task.slug not in executed_tasks:
                executed_tasks.append(task.slug)
            missing_tasks = [slug for slug in state.missing_tasks if slug != task.slug]
            update_batch_state(
                state,
                state_file,
                current_task=task.slug,
                current_phase="achieved",
                executed_tasks=executed_tasks,
                missing_tasks=missing_tasks,
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

    update_batch_state(
        state,
        state_file,
        current_task=None,
        current_phase="completed",
        last_error=state.last_error if state.missing_tasks else None,
    )

    print(f"executed tasks: {state.executed_tasks}")
    print(f"missing tasks: {state.missing_tasks}")
    return 0 if not state.missing_tasks else 1


async def run_managed_single_task(args: argparse.Namespace) -> int:
    task = ManagedTask(
        image=args.task_image, slug=task_slug_from_image(args.task_image)
    )
    structured_log_path = (
        Path(args.structured_log_file)
        if args.structured_log_file
        else _structured_log_path_for_task(Path(args.structured_log_dir), task)
    )
    _ensure_parent_dir(structured_log_path)

    try:
        outcome = await run_managed_task(
            task,
            model_name=args.model,
            use_codex_provider=args.provider == "codex",
            verbose=args.verbose,
            log_file_path=args.log_file,
            structured_log_file_path=str(structured_log_path),
            max_cycles=args.max_cycles,
            cycle_sleep_seconds=args.cycle_sleep,
            server_hostname=args.server_hostname,
            init_timeout_seconds=args.init_timeout,
        )
    except Exception as exc:
        outcome = ManagedTaskOutcome(task=task, achieved=False, error=str(exc))
    if outcome.achieved:
        return 0

    print(outcome.error or "Task failed.")
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

    agent = create_agent(
        container_name=args.container,
        model_name=args.model,
        use_codex_provider=args.provider == "codex",
        verbose=args.verbose,
        log_file_path=args.log_file,
        structured_log_file_path=args.structured_log_file,
    )

    summary = await run_cycles(
        agent, max_cycles=args.max_cycles, cycle_sleep_seconds=args.cycle_sleep
    )
    return 0 if summary.desire_status == "achieved" else 1


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
    parser.add_argument("--model", default="gpt-5.3-codex", help="Model name")
    parser.add_argument(
        "--provider",
        choices=["codex", "native"],
        default="codex",
        help="Use Codex OAuth provider or pass model string directly to PydanticAI",
    )
    parser.add_argument("--max-cycles", type=int, default=30, help="Maximum BDI cycles")
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

    args = parser.parse_args()

    if args.task_image and args.tasks_file:
        parser.error("Use either --task-image or --tasks-file, not both.")
    if args.tasks_file and args.structured_log_file:
        parser.error(
            "--structured-log-file is only supported for manual or --task-image runs."
        )
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
