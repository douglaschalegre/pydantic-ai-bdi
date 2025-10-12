import asyncio
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from bdi import BDI
from bdi.schemas import Intention, IntentionStep
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
import os


@dataclass
class DesireState:
    id: str
    text: str
    status: str  # pending | in_progress | satisfied


@dataclass
class IntentionState:
    id: str
    text: str
    active: bool
    paused: bool = False


@dataclass
class AgentSnapshot:
    agent_id: str
    status: str
    cycle_count: int
    last_progress_at: Optional[str]
    desires: List[DesireState]
    intentions: List[IntentionState]
    active_intention_id: Optional[str]
    created_at: str
    brief: str


@dataclass
class ChatMessage:
    id: str
    at: str
    sender: str
    content: str


@dataclass
class Event:
    type: str
    at: str
    payload: Dict[str, Any]


class ManagedAgent:
    def __init__(self, agent_id: str, bdi: BDI, brief: str):
        self.agent_id = agent_id
        self.bdi = bdi
        self.status = "running"
        self.cycle_count = 0
        self.last_progress_at: Optional[str] = None
        self.event_queue: asyncio.Queue[Event] = asyncio.Queue()
        self.task: Optional[asyncio.Task] = None
        self.stop_flag = False
        self.created_at = iso_now()
        self.brief = brief
        # previous state caches for diff emission
        self._prev_desires: Dict[str, Dict[str, str]] = {}
        # intention cache keyed by intention id -> {text, active}
        self._prev_intentions: Dict[str, Dict[str, Any]] = {}

    async def run(self):
        while not self.stop_flag and self.status == "running":
            self.cycle_count += 1
            await self.emit("cycle.started", {"cycle": self.cycle_count})
            try:
                await self.bdi.bdi_cycle()
                self.last_progress_at = iso_now()
                # After cycle, compute diffs and emit events
                await self._emit_state_diffs()
                # Heartbeat chat message for debugging SSE visibility
                await self.emit(
                    "chat.message",
                    {
                        "message": {
                            "id": str(uuid.uuid4()),
                            "at": iso_now(),
                            "sender": "system",
                            "content": f"Heartbeat after cycle {self.cycle_count}",
                        }
                    },
                )
                await self.emit("cycle.completed", {"cycle": self.cycle_count})
            except Exception as e:  # noqa
                self.status = "error"
                await self.emit("error", {"error": str(e)})
                break
            await asyncio.sleep(1)

    async def emit(self, type_: str, payload: Dict[str, Any]):
        await self.event_queue.put(Event(type=type_, at=iso_now(), payload=payload))

    async def _emit_state_diffs(self):  # noqa: C901
        """Emit granular updates for desires and intentions with stable IDs.

        - desire.updated: for each desire whose text or status changed
        - intention.updated: for each intention whose text or active flag changed
        - chat.message: summary line when an intention step advances or completes
        """
        # ----- Desires -----
        status_map = {
            "pending": "pending",
            "active": "in_progress",
            "achieved": "satisfied",
            "failed": "in_progress",  # no failed state surfaced yet
        }
        for idx, d in enumerate(self.bdi.desires):
            desire_id = getattr(d, "id", None) or f"d{idx}"  # align with snapshot ids
            desc = getattr(d, "description", str(d))
            raw_status = getattr(d, "status", "pending")
            status_val = getattr(raw_status, "value", str(raw_status)).lower()
            mapped = status_map.get(status_val, "in_progress")
            prev = self._prev_desires.get(desire_id)
            if not prev or prev["text"] != desc or prev["status"] != mapped:
                await self.emit(
                    "desire.updated",
                    {"desire": {"id": desire_id, "text": desc, "status": mapped}},
                )
            self._prev_desires[desire_id] = {"text": desc, "status": mapped}

        # ----- Intentions -----
        # Build summary similar to snapshot mapping
        for idx, it in enumerate(self.bdi.intentions):
            intention_id = f"i{idx}"
            # High-level description (WHAT) kept in it.description; fallback to desire id
            high_level = (
                getattr(it, "description", None) or f"Intention for {it.desire_id}"
            )
            # Executing step (HOW) for chat only
            try:
                if it.current_step < len(it.steps):
                    executing_step = it.steps[it.current_step].description
                else:
                    executing_step = "(Completed)"
            except Exception:  # pragma: no cover
                executing_step = "(Unknown step)"
            active = idx == 0
            prev_it = self._prev_intentions.get(intention_id)
            changed = (
                not prev_it
                or prev_it["text"] != high_level
                or prev_it["active"] != active
            )
            if changed:
                await self.emit(
                    "intention.updated",
                    {
                        "intention": {
                            "id": intention_id,
                            "text": high_level,
                            "active": active,
                        }
                    },
                )
            # Emit chat if step advanced (compare executing_step) when active
            prev_step = prev_it.get("executing_step") if prev_it else None
            if active and executing_step != prev_step:
                await self.emit(
                    "chat.message",
                    {
                        "message": {
                            "id": str(uuid.uuid4()),
                            "at": iso_now(),
                            "sender": "agent",
                            "content": f"Cycle {self.cycle_count}: Step -> {executing_step}",
                        }
                    },
                )
                if executing_step == "(Completed)":
                    await self.emit(
                        "chat.message",
                        {
                            "message": {
                                "id": str(uuid.uuid4()),
                                "at": iso_now(),
                                "sender": "agent",
                                "content": f"Cycle {self.cycle_count}: Intention '{high_level}' completed.",
                            }
                        },
                    )
            self._prev_intentions[intention_id] = {
                "text": high_level,
                "active": active,
                "executing_step": executing_step,
            }

        # NOTE: We currently do not emit deletions; if intentions/desires shrink, UI will reflect on next snapshot fetch.


class AgentManager:
    def __init__(self):
        self.agents: Dict[str, ManagedAgent] = {}
        self._loop = asyncio.get_event_loop()

    def _create_model(self) -> OpenAIModel:
        # Minimal placeholder; expects OPENAI_API_KEY
        return OpenAIModel(
            "gpt-4o", provider=OpenAIProvider(api_key=os.getenv("OPENAI_API_KEY"))
        )

    async def create_agent(self, brief: str) -> ManagedAgent:
        agent_id = f"a_{uuid.uuid4().hex[:8]}"
        # TODO: Replace with NL->desires extraction; placeholder single desire/intention
        model = self._create_model()
        bdi = BDI(
            model,
            desires=[brief],
            intentions=["Initial analysis"],
            verbose=False,
            enable_human_in_the_loop=False,
        )
        # Fallback placeholder intentions when no OpenAI key (so UI isn't empty)
        if not os.getenv("OPENAI_API_KEY") and not bdi.intentions:
            for desire in bdi.desires:
                try:
                    bdi.intentions.append(
                        Intention(
                            desire_id=desire.id,
                            description=f"Fulfill desire: {desire.description}",
                            steps=[
                                IntentionStep(
                                    description="Placeholder step until LLM intention generation is enabled",
                                    is_tool_call=False,
                                )
                            ],
                        )
                    )
                except Exception:
                    # Silent fallback; if construction fails we just proceed without intentions
                    pass
        managed = ManagedAgent(agent_id, bdi, brief=brief)
        managed.task = self._loop.create_task(managed.run())
        self.agents[agent_id] = managed
        return managed

    def get_agent(self, agent_id: str) -> Optional[ManagedAgent]:
        return self.agents.get(agent_id)

    def snapshot(self, agent_id: str) -> Optional[AgentSnapshot]:
        ma = self.agents.get(agent_id)
        if not ma:
            return None
        # Placeholder: extract current internal state references directly from bdi
        # Map internal Desire objects -> frontend DesireState
        status_map = {
            "pending": "pending",
            "active": "in_progress",
            "achieved": "satisfied",
            "failed": "in_progress",  # no distinct failed state in frontend yet
        }
        desires = []
        for i, d in enumerate(ma.bdi.desires):
            # d is a Desire object (has .description, .status)
            raw_status = getattr(d.status, "value", str(d.status)).lower()
            mapped_status = status_map.get(raw_status, "in_progress")
            desires.append(
                DesireState(
                    id=f"d{i}",
                    text=d.description if hasattr(d, "description") else str(d),
                    status=mapped_status,
                )
            )

        # Map Intention objects -> simple textual summary
        intentions = []
        for i, it in enumerate(ma.bdi.intentions):
            # Show high-level description only (not current step)
            high_level = (
                getattr(it, "description", None) or f"Intention for {it.desire_id}"
            )
            intentions.append(
                IntentionState(id=f"i{i}", text=high_level, active=(i == 0))
            )
        return AgentSnapshot(
            agent_id=ma.agent_id,
            status=ma.status,
            cycle_count=ma.cycle_count,
            last_progress_at=ma.last_progress_at,
            desires=desires,
            intentions=intentions,
            active_intention_id=intentions[0].id if intentions else None,
            created_at=ma.created_at,
            brief=ma.brief,
        )

    def list_snapshots(self) -> List[AgentSnapshot]:
        return [
            self.snapshot(aid)
            for aid in self.agents.keys()
            if self.snapshot(aid) is not None
        ]


def iso_now() -> str:
    """Return current UTC time in ISO 8601 format with 'Z'."""
    # Use datetime to ensure proper ISO format rather than loop time float
    import datetime as _dt

    return _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


agent_manager = AgentManager()
