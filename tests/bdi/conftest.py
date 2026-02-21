from collections import deque
from types import SimpleNamespace

import pytest

from bdi.schemas import BeliefSet, Desire, DesireStatus, Intention, IntentionStep


class StubBDIAgent:
    def __init__(self):
        self.beliefs = BeliefSet()
        self.desires = []
        self.intentions = deque()
        self.initial_intention_guidance = []
        self.enable_human_in_the_loop = False
        self.verbose = False
        self.tool_configs = {}
        self._queued_run_outputs = deque()

    def add_desire(
        self,
        *,
        desire_id: str,
        description: str,
        status: DesireStatus = DesireStatus.PENDING,
        priority: float = 0.5,
    ) -> Desire:
        desire = Desire(
            id=desire_id,
            description=description,
            priority=priority,
            status=status,
        )
        self.desires.append(desire)
        return desire

    def set_current_intention(
        self,
        *,
        desire_id: str,
        step_descriptions: list[str],
        current_step: int = 0,
    ) -> Intention:
        intention = Intention(
            desire_id=desire_id,
            description=f"Intention for {desire_id}",
            steps=[IntentionStep(description=s) for s in step_descriptions],
            current_step=current_step,
        )
        self.intentions = deque([intention])
        return intention

    def queue_run_output(self, output) -> None:
        self._queued_run_outputs.append(SimpleNamespace(output=output))

    async def run(self, *_args, **_kwargs):
        if not self._queued_run_outputs:
            raise AssertionError("StubBDIAgent.run called without queued output")
        return self._queued_run_outputs.popleft()


@pytest.fixture
def stub_agent() -> StubBDIAgent:
    return StubBDIAgent()
