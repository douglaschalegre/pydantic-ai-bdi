from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Protocol


FINAL_CYCLE_STATUSES = frozenset({"terminal", "stopped", "interrupted"})
TERMINAL_DESIRE_STATUSES = frozenset({"achieved", "failed"})
SUCCESS_OUTCOMES = frozenset({"achieved", "terminal"})
MAX_CYCLES_OUTCOME = "max_cycles_reached"


class BDIInterface(Protocol):
    desires: Sequence[object]

    async def bdi_cycle(self) -> str: ...


@dataclass(frozen=True)
class CycleProgress:
    cycle: int
    max_cycles: int
    cycle_status: str
    desire_status: str | None


@dataclass(frozen=True)
class RunSummary:
    outcome: str
    cycles_run: int
    max_cycles: int
    cycle_status: str | None
    desire_status: str | None

    @property
    def succeeded(self) -> bool:
        return self.outcome in SUCCESS_OUTCOMES


ProgressCallback = Callable[[CycleProgress], Awaitable[None] | None]


def status_name(status: object) -> str | None:
    if status is None:
        return None
    value = getattr(status, "value", status)
    return str(value)


def primary_desire_status(agent: BDIInterface) -> str | None:
    if not agent.desires:
        return None
    return status_name(getattr(agent.desires[0], "status", None))


async def drive_bdi_cycles(
    agent: BDIInterface,
    *,
    max_cycles: int,
    sleep_seconds: float = 0,
    progress_callback: ProgressCallback | None = None,
    stop_on_terminal_desire: bool = True,
) -> RunSummary:
    if max_cycles < 1:
        raise ValueError("max_cycles must be at least 1")

    last_cycle_status: str | None = None
    desire_status = primary_desire_status(agent)
    for cycle in range(1, max_cycles + 1):
        last_cycle_status = status_name(await agent.bdi_cycle())
        desire_status = primary_desire_status(agent)
        progress = CycleProgress(
            cycle=cycle,
            max_cycles=max_cycles,
            cycle_status=last_cycle_status or "unknown",
            desire_status=desire_status,
        )
        if progress_callback is not None:
            callback_result = progress_callback(progress)
            if callback_result is not None:
                await callback_result

        outcome = None
        if stop_on_terminal_desire and desire_status in TERMINAL_DESIRE_STATUSES:
            outcome = desire_status
        elif last_cycle_status in FINAL_CYCLE_STATUSES:
            outcome = last_cycle_status
        if outcome is not None:
            return RunSummary(
                outcome=outcome,
                cycles_run=cycle,
                max_cycles=max_cycles,
                cycle_status=last_cycle_status,
                desire_status=desire_status,
            )
        if cycle < max_cycles and sleep_seconds:
            await asyncio.sleep(sleep_seconds)

    return RunSummary(
        outcome=MAX_CYCLES_OUTCOME,
        cycles_run=max_cycles,
        max_cycles=max_cycles,
        cycle_status=last_cycle_status,
        desire_status=desire_status,
    )
