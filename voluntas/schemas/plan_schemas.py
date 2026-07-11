"""Plan-related schemas for executable BDI strategy."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

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

    def current_step(self) -> Optional[PlanStep]:
        """Return the currently executable Plan Step, if one exists."""
        if self.is_complete():
            return None
        return self.steps[self.current_step_index]

    def remaining_steps_after_current(self) -> List[PlanStep]:
        """Return Plan Steps that follow the currently executable Plan Step."""
        return self.steps[self.current_step_index + 1 :]

    def modify_current_step(self, modifications: Dict[str, Any]) -> None:
        """Apply field updates to the current Plan Step."""
        current_step = self.current_step()
        if current_step is None:
            raise IndexError("No current Plan Step to modify")

        unknown_fields = set(modifications) - set(PlanStep.model_fields)
        if unknown_fields:
            field_list = ", ".join(sorted(unknown_fields))
            raise ValueError(f"Unknown Plan Step field(s): {field_list}")

        self.steps[self.current_step_index] = PlanStep.model_validate(
            current_step.model_dump() | modifications
        )

    def replace_current_step(self, new_steps: List[PlanStep]) -> None:
        """Replace the current Plan Step with one or more Plan Steps."""
        if self.current_step() is None:
            raise IndexError("No current Plan Step to replace")
        self.steps = (
            self.steps[: self.current_step_index]
            + new_steps
            + self.steps[self.current_step_index + 1 :]
        )
        self.status = PlanStatus.ACTIVE

    def insert_steps_before_current(self, new_steps: List[PlanStep]) -> None:
        """Insert Plan Steps before the current Plan Step without changing commitment."""
        if self.current_step() is None:
            raise IndexError("No current Plan Step before which to insert")
        self.steps = (
            self.steps[: self.current_step_index]
            + new_steps
            + self.steps[self.current_step_index :]
        )
        self.status = PlanStatus.ACTIVE

    def insert_steps_after_current(self, new_steps: List[PlanStep]) -> None:
        """Insert Plan Steps immediately after the current Plan Step."""
        if self.current_step() is None:
            raise IndexError("No current Plan Step after which to insert")
        insert_point = self.current_step_index + 1
        self.steps = self.steps[:insert_point] + new_steps + self.steps[insert_point:]
        self.status = PlanStatus.ACTIVE

    def replace_remaining_steps(self, new_steps: List[PlanStep]) -> None:
        """Replace the current and future Plan Steps, preserving completed steps."""
        self.steps = self.steps[: self.current_step_index] + new_steps
        self.status = PlanStatus.ACTIVE

    def repair(self, repaired_steps: List[PlanStep]) -> None:
        """Repair current and future work while preserving progress and history."""
        self.replace_remaining_steps(repaired_steps)

    def replace(self, replacement_steps: List[PlanStep]) -> None:
        """Replace executable work while preserving the Plan's execution history."""
        self.steps = replacement_steps
        self.current_step_index = 0
        self.status = PlanStatus.ACTIVE

    def activate(self) -> None:
        """Make a non-exhausted Plan executable."""
        if self.is_complete():
            raise ValueError("A completed Plan cannot be activated without replacement work")
        self.status = PlanStatus.ACTIVE

    def fail(self) -> None:
        """Mark this Plan as requiring repair, replacement, or abandonment."""
        self.status = PlanStatus.FAILED

    def mark_completed(self) -> None:
        """Mark an exhausted Plan completed."""
        if not self.is_complete():
            raise ValueError("A Plan with remaining steps cannot be completed")
        self.status = PlanStatus.COMPLETED

    def advance_current_step(self) -> bool:
        """Advance and return whether the Plan became complete."""
        if self.current_step() is None:
            raise IndexError("No current Plan Step to advance")
        self.current_step_index += 1
        if self.is_complete():
            self.status = PlanStatus.COMPLETED
            return True
        self.status = PlanStatus.ACTIVE
        return False

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

    def record_outcome_and_advance(
        self,
        step: PlanStep,
        result: str,
        beliefs_updated: Dict[str, Any],
    ) -> bool:
        """Record a successful current step and advance atomically."""
        if step is not self.current_step():
            raise ValueError("Outcome does not belong to the current Plan Step")
        self.add_to_history(step, result, True, beliefs_updated)
        return self.advance_current_step()

    def record_failure(
        self,
        step: PlanStep,
        result: str,
        beliefs_updated: Dict[str, Any],
    ) -> None:
        """Record a failed current step and transition the Plan to failed."""
        if step is not self.current_step():
            raise ValueError("Outcome does not belong to the current Plan Step")
        self.add_to_history(step, result, False, beliefs_updated)
        self.fail()


__all__ = [
    "PlanStatus",
    "PlanStep",
    "PlanStepHistory",
    "Plan",
]
