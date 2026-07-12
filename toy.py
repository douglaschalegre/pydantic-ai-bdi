from __future__ import annotations

import asyncio
from collections.abc import Sequence
import json
from pathlib import Path
import sys
import time

from dotenv import load_dotenv
from pydantic_ai.mcp import MCPServerStdio  # noqa: F401

from litellm_proxy import create_litellm_model
from voluntas import BDI, BDIUsageTracker
from runners.bdi import SUCCESS_OUTCOMES, drive_bdi_cycles
from sbench_toy.config import RunConfig, RunnerConfigError, get_task_path, parse_config
from sbench_toy.tools import run_command

load_dotenv()


MAX_CYCLES = 30
CYCLE_SLEEP_SECONDS = 2.0
EXIT_SUCCESS = 0
EXIT_TASK_FAILURE = 1
EXIT_CONFIG_ERROR = 2


def create_model(config: RunConfig):
    return create_litellm_model(config.model_name)


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
        stream_model_requests=True,
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
    active_intention = getattr(agent, "active_intention", None)

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
        "intentions": int(active_intention is not None),
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
            summary = await drive_bdi_cycles(
                agent,
                max_cycles=MAX_CYCLES,
                sleep_seconds=CYCLE_SLEEP_SECONDS,
                progress_callback=lambda event: print(
                    f"Cycle {event.cycle}/{event.max_cycles}"
                ),
            )
            cycles_run = summary.cycles_run
            outcome = summary.outcome
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
                "type": "voluntas.run.completed",
                "model": config.model_name,
                "task": task_slug,
                "outcome": outcome,
                "cycles": {"run": cycles_run, "max": MAX_CYCLES},
                "elapsed_seconds": elapsed_seconds,
                "usage": usage_tracker.usage_summary(),
                "cost": usage_tracker.cost_summary(),
                "voluntas": _summarize_bdi_agent(agent),
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
