from __future__ import annotations

import asyncio
from collections.abc import Sequence
import json
from pathlib import Path
import sys
import time

from dotenv import load_dotenv
from pydantic_ai.mcp import MCPServerStdio  # noqa: F401

from bdi import BDI, BDIUsageTracker
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
    model: object,
    task_path: Path,
    config: RunConfig,
    usage_tracker: BDIUsageTracker | None = None,
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
        usage_tracker=usage_tracker,
        emit_run_events_to_stdout=True,
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


def _status_value(status: object) -> object:
    return getattr(status, "value", status)


def _summarize_bdi_agent(agent: BDI | None) -> dict[str, object] | None:
    if agent is None:
        return None

    beliefs = getattr(agent, "beliefs", None)
    belief_items = getattr(beliefs, "beliefs", {}) if beliefs is not None else {}
    desires = getattr(agent, "desires", []) or []
    intentions = getattr(agent, "intentions", []) or []

    return {
        "cycle_count": getattr(agent, "cycle_count", None),
        "beliefs": len(belief_items),
        "desires": [
            {
                "id": getattr(desire, "id", None),
                "status": _status_value(getattr(desire, "status", None)),
            }
            for desire in desires
        ],
        "intentions": len(intentions),
    }


async def run_task(model: object, task_path: Path, config: RunConfig) -> str:
    task_slug = task_path.name
    usage_tracker = BDIUsageTracker(model_name=config.model_name)
    agent: BDI | None = None
    started_at = time.monotonic()
    cycles_run = 0
    outcome = "max_cycles_reached"

    print(f"Running SBench task {task_slug}")
    print(f"Task folder: {task_path}")

    try:
        agent = create_agent(
            model,
            task_path,
            config,
            usage_tracker=usage_tracker,
        )
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
    print(
        json.dumps(
            {
                "type": "bdi.run.completed",
                "model": config.model_name,
                "task": task_slug,
                "outcome": outcome,
                "cycles": {"run": cycles_run, "max": MAX_CYCLES},
                "elapsed_seconds": elapsed_seconds,
                "usage": usage_tracker.usage_summary(),
                "cost": usage_tracker.cost_summary(),
                "bdi": _summarize_bdi_agent(agent),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return outcome


async def run_benchmark(config: RunConfig) -> int:
    task_path = get_task_path(config)
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
