from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path
import sys
import time

from dotenv import load_dotenv
from pydantic_ai.mcp import MCPServerStdio

from bdi import BDI
from bdi.cycle import is_final_cycle_status
from bdi.schemas import DesireStatus
from sbench_toy.config import RunConfig, RunnerConfigError, get_task_path, parse_config
from sbench_toy.tools import run_command

load_dotenv()


MAX_CYCLES = 30
CYCLE_SLEEP_SECONDS = 2.0
SUCCESS_OUTCOMES = frozenset({DesireStatus.ACHIEVED.value, "terminal"})
EXIT_SUCCESS = 0
EXIT_TASK_FAILURE = 1
EXIT_CONFIG_ERROR = 2


def create_model(config: RunConfig):
    from codex import CodexModel, CodexProvider

    return CodexModel(config.model_name, provider=CodexProvider())


def create_agent(
    model: object, task_path: Path, config: RunConfig, log_path: Path
) -> BDI:
    agent = BDI(
        model,
        desires=[
            (
                f"Complete the SBench task in {task_path}. "
                "Inspect task.md and any non-hidden local task files. "
                "Do not read hidden SBench evaluation files. "
                "Create all requested deliverables in the answer/ folder. "
                "Use the filesystem MCP server and run_in_task terminal tool as needed. "
                "Before stopping, verify answer/ contains the requested files."
            )
        ],
        intentions=[],
        verbose=config.verbose,
        enable_human_in_the_loop=False,
        log_file_path=str(log_path),
        mcp_servers=[
            # MCPServerStdio(
            #     "npx",
            #     args=["-y", "@modelcontextprotocol/server-filesystem", str(task_path)],
            #     tool_prefix="fs",
            #     timeout=60,
            # )
        ],
    )

    @agent.tool_plain
    def run_in_task(
        command: str,
        timeout_seconds: int = config.command_timeout_seconds,
    ) -> str:
        """Run a shell command in this SBench task folder."""

        return run_command(
            task_path,
            command,
            timeout_seconds=timeout_seconds,
            max_timeout_seconds=config.command_timeout_seconds,
        )

    return agent


async def run_task(model: object, task_path: Path, config: RunConfig) -> str:
    task_slug = task_path.name
    log_path = config.output_dir / f"{task_slug}.log"
    started_at = time.monotonic()
    cycles_run = 0
    outcome = "max_cycles_reached"

    print(f"Running SBench task {task_slug}")
    print(f"Task folder: {task_path}")
    print(f"Log file: {log_path}")

    try:
        agent = create_agent(model, task_path, config, log_path)
        async with agent.run_mcp_servers():
            for cycle in range(1, MAX_CYCLES + 1):
                cycles_run = cycle
                print(f"Cycle {cycle}/{MAX_CYCLES}")
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
        print(f"[ERROR] Task {task_slug} failed: {exc}")

    elapsed_seconds = int(time.monotonic() - started_at)
    print(
        f"Task result: {outcome}; cycles={cycles_run}/{MAX_CYCLES}; "
        f"elapsed_seconds={elapsed_seconds}"
    )
    print(f"Answer folder: {task_path / 'answer'}")
    return outcome


async def run_benchmark(config: RunConfig) -> int:
    task_path = get_task_path(config)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Model: {config.model_name}")
    print(f"SBench root: {config.sbench_root}")
    outcome = await run_task(create_model(config), task_path, config)
    return EXIT_SUCCESS if outcome in SUCCESS_OUTCOMES else EXIT_TASK_FAILURE


async def main(argv: Sequence[str] | None = None) -> int:
    config = parse_config(argv)
    try:
        return await run_benchmark(config)
    except RunnerConfigError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
