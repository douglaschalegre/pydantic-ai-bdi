from __future__ import annotations

import asyncio
from pathlib import Path
import subprocess
import time

from dotenv import load_dotenv
from pydantic_ai.mcp import MCPServerStdio

from bdi import BDI
from bdi.cycle import is_final_cycle_status
from bdi.schemas import DesireStatus
from codex import CodexModel, CodexProvider


load_dotenv()


# Hardcoded toy demo configuration.
MODEL_NAME = "gpt-5.2"
SBENCH_ROOT = Path("/Users/douglas/code/masters/sbench")
TASKS_ROOT = SBENCH_ROOT / "tasks"
OUTPUT_DIR = Path(__file__).resolve().parent / "output" / "sbench-toy"

MAX_CYCLES = 30
CYCLE_SLEEP_SECONDS = 2.0
COMMAND_TIMEOUT_SECONDS = 180
VERBOSE = True
SKIP_TASKS: set[str] = set()


def discover_tasks() -> list[Path]:
    if not TASKS_ROOT.is_dir():
        raise RuntimeError(f"SBench tasks directory not found: {TASKS_ROOT}")

    tasks = [
        path
        for path in sorted(TASKS_ROOT.iterdir())
        if path.is_dir() and (path / "task.md").is_file()
    ]
    if not tasks:
        raise RuntimeError(f"No SBench tasks with task.md found under {TASKS_ROOT}")
    return tasks


def build_filesystem_server(task_path: Path) -> MCPServerStdio:
    return MCPServerStdio(
        "npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", str(task_path)],
        tool_prefix="fs",
        timeout=60,
    )


def run_command(
    task_path: Path,
    command: str,
    timeout_seconds: int = COMMAND_TIMEOUT_SECONDS,
) -> str:
    """Run a shell command starting in the task folder."""

    if not command.strip():
        return "Command cannot be empty."

    try:
        timeout = max(1, min(int(timeout_seconds), COMMAND_TIMEOUT_SECONDS))
    except (TypeError, ValueError):
        timeout = COMMAND_TIMEOUT_SECONDS

    try:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=str(task_path),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")

        output = "\n".join(part.strip() for part in (stdout, stderr) if part).strip()
        if output:
            return f"Command timed out after {timeout} seconds.\n{output}"
        return f"Command timed out after {timeout} seconds."
    except Exception as exc:
        return f"Command failed to start: {exc}"

    output_parts = []
    if completed.stdout:
        output_parts.append(completed.stdout.strip())
    if completed.stderr:
        output_parts.append(f"[stderr]\n{completed.stderr.strip()}")
    output = "\n".join(output_parts).strip() or "(no output)"

    if completed.returncode == 0:
        return output
    return f"Command exited with code {completed.returncode}.\n{output}"


def create_agent(model: CodexModel, task_path: Path, log_path: Path) -> BDI:
    agent = BDI(
        model,
        desires=[
            (
                f"Complete the SBench task in {task_path}. "
                "Inspect task.md and any other local task files. "
                "Create all requested deliverables in the answer/ folder. "
                "Use the filesystem MCP server and run_in_task terminal tool as needed. "
                "Before stopping, verify answer/ contains the requested files."
            )
        ],
        intentions=[],
        verbose=VERBOSE,
        enable_human_in_the_loop=False,
        log_file_path=str(log_path),
        mcp_servers=[build_filesystem_server(task_path)],
    )

    @agent.tool_plain
    def run_in_task(
        command: str,
        timeout_seconds: int = COMMAND_TIMEOUT_SECONDS,
    ) -> str:
        """Run a shell command in this SBench task folder.

        Commands start with cwd set to the task folder, but this is not a sandbox.
        """

        return run_command(task_path, command, timeout_seconds=timeout_seconds)

    return agent


async def run_task(model: CodexModel, task_path: Path, output_dir: Path) -> None:
    task_slug = task_path.name
    log_path = output_dir / f"{task_slug}.log"
    task_started_at = time.monotonic()

    print(f"\n=== SBench Task: {task_slug} ===")
    print(f"Task folder: {task_path}")
    print(f"Answer folder: {task_path / 'answer'}")

    cycles_run = 0
    outcome = "max_cycles_reached"
    error_message: str | None = None

    try:
        agent = create_agent(model, task_path, log_path)
        async with agent.run_mcp_servers():
            for cycle in range(1, MAX_CYCLES + 1):
                cycles_run = cycle
                print(f"\n----- {task_slug} | Cycle {cycle}/{MAX_CYCLES} -----")
                cycle_status = await agent.bdi_cycle()

                desire_status = agent.desires[0].status if agent.desires else None
                if desire_status in (DesireStatus.ACHIEVED, DesireStatus.FAILED):
                    outcome = desire_status.value
                    break
                if is_final_cycle_status(cycle_status):
                    outcome = cycle_status
                    break

                await asyncio.sleep(CYCLE_SLEEP_SECONDS)
    except Exception as exc:
        outcome = "error"
        error_message = str(exc)
        print(f"[ERROR] Task {task_slug} failed: {exc}")
        print("[INFO] Continuing to the next task.")

    print(f"\n=== SBench Task Result: {task_slug} ===")
    print(f"Status: {outcome}")
    print(f"Cycles Run: {cycles_run}/{MAX_CYCLES}")
    elapsed_seconds = int(time.monotonic() - task_started_at)
    elapsed_minutes, remaining_seconds = divmod(elapsed_seconds, 60)
    print(f"Time: {elapsed_minutes} min {remaining_seconds} sec")
    if error_message:
        print(f"Error: {error_message}")
    print(f"Answer Folder: {task_path / 'answer'}")
    print(f"Log File: {log_path}")


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tasks = [task for task in discover_tasks() if task.name not in SKIP_TASKS]
    if not tasks:
        print("No SBench tasks selected. Check TASKS_ROOT or SKIP_TASKS.")
        return

    print("=== SBench BDI + Filesystem Toy Run ===")
    print(f"Model: {MODEL_NAME}")
    print(f"SBench Root: {SBENCH_ROOT}")
    print(f"Tasks Root: {TASKS_ROOT}")
    print(f"Tasks: {', '.join(task.name for task in tasks)}")
    print(f"Max Cycles Per Task: {MAX_CYCLES}")
    print(f"Command Timeout Seconds: {COMMAND_TIMEOUT_SECONDS}")
    print(f"Logs Directory: {OUTPUT_DIR}")

    provider = CodexProvider()
    model = CodexModel(MODEL_NAME, provider=provider)

    for task in tasks:
        await run_task(model, task, OUTPUT_DIR)

    print("\n=== SBench Toy Run Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
