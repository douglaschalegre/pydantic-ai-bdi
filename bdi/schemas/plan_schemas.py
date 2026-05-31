"""Plan-related schemas for executable BDI strategy."""

from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field


class PlanStatus(str, Enum):
    """Lifecycle status for an Intention-owned executable Plan."""

    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


class PlanStep(BaseModel):
    """A single executable step within a Plan."""

    description: str = Field(
        description="Detailed description of the step (HOW to perform it). Can be natural language or a tool call hint."
    )
    is_tool_call: bool = Field(
        default=False,
        description="Set to true if this step involves calling a specific tool.",
    )
    tool_name: Optional[str] = Field(
        default=None,
        description="The name of the tool to call, if is_tool_call is true.",
    )
    tool_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Parameters for the tool call, if is_tool_call is true.",
    )


class PlanStepHistory(BaseModel):
    """Tracks the history of executed Plan Steps and their outcomes."""

    step_description: str
    step_number: int
    result: str
    success: bool
    timestamp: float
    beliefs_updated: Dict[str, Any]


class Plan(BaseModel):
    """Executable strategy owned by an Intention."""

    steps: List[PlanStep]
    current_step_index: int = 0
    status: PlanStatus = PlanStatus.ACTIVE
    step_history: List[PlanStepHistory] = Field(default_factory=list)

    def is_complete(self) -> bool:
        """Return True when every Plan Step has been advanced past."""
        return self.current_step_index >= len(self.steps)

    def advance_current_step(self, logger: Callable, *, desire_id: str) -> None:
        """Advance to the next Plan Step and mark the Plan completed when exhausted."""
        self.current_step_index += 1
        if self.is_complete():
            self.status = PlanStatus.COMPLETED
            message = f"Plan for desire '{desire_id}' completed all Plan Steps"
        else:
            message = (
                f"Plan for desire '{desire_id}' advanced to Plan Step "
                f"{self.current_step_index + 1}"
            )

        logger(
            types=["intentions"],
            message=message,
        )

    def add_to_history(
        self,
        step: PlanStep,
        result: str,
        success: bool,
        beliefs_updated: Dict[str, Any],
    ) -> None:
        """Record a Plan Step execution in Plan Step History."""
        self.step_history.append(
            PlanStepHistory(
                step_description=step.description,
                step_number=self.current_step_index,
                result=result,
                success=success,
                timestamp=datetime.now().timestamp(),
                beliefs_updated=beliefs_updated,
            )
        )


IntentionStep = PlanStep
StepHistory = PlanStepHistory


__all__ = [
    "PlanStatus",
    "PlanStep",
    "PlanStepHistory",
    "Plan",
    "IntentionStep",
    "StepHistory",
]
