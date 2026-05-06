"""BDI experiment template (participant-facing).

Copy to: benchmarks/experiments/bdi/<task_id>/experiment-<participant>.py
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import sys

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

from pydantic_ai.mcp import MCPServerStdio

from bdi.agent import BDI
from bdi.cycle import is_final_cycle_status
from benchmarks.experiments.bdi import runner


def build_agent(model, mcp_servers: List[MCPServerStdio] | None = None) -> BDI:
    """Return a configured BDI agent for your task."""
    desires = [
        "Read the pyproject.toml file and report the number of lines."
    ]
    return BDI(
        model=model,
        desires=desires,
        intentions=[
            "Read pyproject.toml",
            "Count lines",
            "Report the line count",
        ],
        mcp_servers=mcp_servers or [],
        verbose=True,
        enable_human_in_the_loop=False,
    )


def get_mcp_servers(repo_path: str):
    repo = Path(repo_path)
    fs_server = MCPServerStdio(
        "npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", str(repo)],
        tool_prefix="fs_bench",
        timeout=60,
    )
    return [fs_server]


async def run_agent(agent, metric_collector):
    max_cycles = 1
    max_cycles = 100
    status = "unknown"
    async with agent.run_mcp_servers():
        for _ in range(max_cycles):
            metric_collector.record_cycle()
            status = await agent.bdi_cycle()
            metric_collector.record_step(success=True)
            if is_final_cycle_status(status):
                break
    return {"success": is_final_cycle_status(status), "status": status}


if __name__ == "__main__":
    runner.main(__file__)
