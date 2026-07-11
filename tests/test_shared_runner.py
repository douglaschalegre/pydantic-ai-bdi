from types import SimpleNamespace

import pytest

from runners.bdi import drive_bdi_cycles


class FakeBDI:
    def __init__(self, cycle_statuses: list[str], desire_status: str = "active"):
        self.cycle_statuses = iter(cycle_statuses)
        self.desires = [SimpleNamespace(status=desire_status)]

    async def bdi_cycle(self) -> str:
        status = next(self.cycle_statuses)
        if status == "mark_achieved":
            self.desires[0].status = "achieved"
            return "executed"
        return status


@pytest.mark.asyncio
async def test_cycle_driver_stops_on_terminal_desire_and_emits_progress() -> None:
    events = []
    summary = await drive_bdi_cycles(
        FakeBDI(["executed", "mark_achieved", "executed"]),
        max_cycles=5,
        progress_callback=events.append,
    )

    assert summary.outcome == "achieved"
    assert summary.cycles_run == 2
    assert summary.succeeded
    assert [event.cycle for event in events] == [1, 2]


@pytest.mark.asyncio
async def test_cycle_driver_classifies_cycle_terminal_and_limit() -> None:
    terminal = await drive_bdi_cycles(FakeBDI(["terminal"]), max_cycles=3)
    limited = await drive_bdi_cycles(FakeBDI(["executed", "executed"]), max_cycles=2)

    assert terminal.outcome == "terminal"
    assert terminal.succeeded
    assert limited.outcome == "max_cycles_reached"
    assert limited.cycles_run == 2
