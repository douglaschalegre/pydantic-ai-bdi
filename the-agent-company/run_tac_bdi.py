from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bdi import BDI
from codex import CodexModel, CodexProvider
from pydantic_ai.mcp import MCPServerStdio


def _run_command(cmd: Sequence[str], timeout_seconds: int) -> str:
    completed = subprocess.run(
        list(cmd),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    output = completed.stdout
    if completed.stderr:
        output = (
            f"{output}\n[stderr]\n{completed.stderr}" if output else completed.stderr
        )
    output = output.strip()
    if completed.returncode != 0:
        return (
            f"Command failed with exit code {completed.returncode}.\n"
            f"Command: {' '.join(cmd)}\n"
            f"Output:\n{output}"
        )
    return output or "(no output)"


def _docker_exec(container: str, command: str, timeout_seconds: int = 180) -> str:
    cmd = ["docker", "exec", container, "/bin/bash", "-lc", command]
    return _run_command(cmd, timeout_seconds=timeout_seconds)


def _build_playwright_server() -> MCPServerStdio:
    return MCPServerStdio(
        "npx",
        args=["-y", "@playwright/mcp@latest"],
        tool_prefix="playwright",
        timeout=300,
    )


def create_agent(
    *,
    container_name: str,
    model_name: str,
    use_codex_provider: bool,
    include_playwright: bool,
    verbose: bool,
    log_file_path: str | None,
) -> BDI:
    model = model_name
    if use_codex_provider:
        provider = CodexProvider()
        model = CodexModel(model_name, provider=provider)

    mcp_servers: list[MCPServerStdio] = []
    if include_playwright:
        mcp_servers.append(_build_playwright_server())

    desire = (
        f"Complete the task described in /instruction/task.md inside docker container '{container_name}'. "
        "Use available tools to inspect instructions, edit files in /workspace, run commands, "
        "and verify results."
    )
    intentions = None

    agent = BDI(
        model=model,
        desires=[desire],
        intentions=intentions,
        verbose=verbose,
        enable_human_in_the_loop=False,
        log_file_path=log_file_path,
        mcp_servers=mcp_servers,
    )

    @agent.tool_plain
    def run_in_tac(command: str, timeout_seconds: int = 180) -> str:
        """Run any shell command in the TAC task container.

        Use this as a generic terminal tool for inspection, edits, and verification.

        Args:
            command: Command to run via `/bin/bash -lc` inside the container.
            timeout_seconds: Timeout in seconds.
        """

        return _docker_exec(container_name, command, timeout_seconds=timeout_seconds)

    return agent


async def run_cycles(agent: BDI, max_cycles: int, cycle_sleep_seconds: float) -> None:
    status = "unknown"
    async with agent.run_mcp_servers():
        for cycle in range(1, max_cycles + 1):
            print(f"\n===== TAC BDI Cycle {cycle}/{max_cycles} =====")
            status = await agent.bdi_cycle()
            if status in ["stopped", "interrupted"]:
                print(f"Agent cycle ended with status: {status}")
                break

            await asyncio.sleep(cycle_sleep_seconds)

    print("\nRun finished.")
    if agent.desires:
        print(f"Final desire status: {agent.desires[0].status.value}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a BDI agent against a TAC task container."
    )
    parser.add_argument(
        "--container",
        default="tac-test",
        help="Docker container name (default: tac-test)",
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
        "--include-playwright",
        action="store_true",
        help="Attach Playwright MCP server for browser tasks",
    )
    parser.add_argument(
        "--log-file",
        default=str(Path(__file__).with_name("tac_bdi_agent.log")),
        help="Path for terminal-mirrored BDI logs",
    )
    return parser.parse_args()


async def _main() -> None:
    args = parse_args()

    # Fast preflight checks so the agent fails with clear messages.
    check = _run_command(
        ["docker", "inspect", "--format", "{{.State.Running}}", args.container], 30
    )
    if "true" not in check.lower():
        raise RuntimeError(
            f"Container '{args.container}' is not running. Start it first, then run this script.\n"
            f"docker inspect output: {check}"
        )

    agent = create_agent(
        container_name=args.container,
        model_name=args.model,
        use_codex_provider=args.provider == "codex",
        include_playwright=args.include_playwright,
        verbose=args.verbose,
        log_file_path=args.log_file,
    )

    await run_cycles(
        agent, max_cycles=args.max_cycles, cycle_sleep_seconds=args.cycle_sleep
    )


if __name__ == "__main__":
    asyncio.run(_main())
