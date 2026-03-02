from typing import Literal

import pytest

from bdi.planning import generate_intentions_from_desires
from bdi.schemas import (
    DesireStatus,
    DetailedStepList,
    IntentionStep,
    PlanJudgementResult,
)


def _queue_stage2_with_judgement(
    stub_agent,
    *,
    step_descriptions: list[str],
    decision: Literal["keep", "merge", "skip"] = "keep",
    reason_category: Literal[
        "already_completed",
        "already_planned",
        "blocked",
        "new_work_needed",
        "other",
    ] = "new_work_needed",
    reason: str = "This introduces required work.",
) -> None:
    stub_agent.queue_run_output(
        DetailedStepList(
            steps=[IntentionStep(description=description) for description in step_descriptions]
        )
    )
    stub_agent.queue_run_output(
        PlanJudgementResult(
            decision=decision,
            reason_category=reason_category,
            reason=reason,
        )
    )


@pytest.mark.asyncio
async def test_explicit_intentions_target_first_actionable_desire(stub_agent) -> None:
    stub_agent.add_desire(
        desire_id="desire_done",
        description="Already done",
        status=DesireStatus.ACHIEVED,
    )
    active_desire = stub_agent.add_desire(
        desire_id="desire_active",
        description="Needs execution",
        status=DesireStatus.ACTIVE,
    )
    stub_agent.initial_intention_guidance = ["Generate report"]
    stub_agent.queue_run_output(
        DetailedStepList(steps=[IntentionStep(description="Collect inputs")])
    )

    await generate_intentions_from_desires(stub_agent)

    assert len(stub_agent.intentions) == 1
    assert stub_agent.intentions[0].desire_id == active_desire.id


@pytest.mark.asyncio
async def test_planning_stage2_uses_prior_plan_context(stub_agent) -> None:
    stub_agent.add_desire(
        desire_id="desire_1",
        description="Do the work",
        status=DesireStatus.ACTIVE,
    )
    stub_agent.initial_intention_guidance = ["First intention", "Second intention"]

    _queue_stage2_with_judgement(
        stub_agent,
        step_descriptions=["Collect repository metadata"],
    )
    _queue_stage2_with_judgement(
        stub_agent,
        step_descriptions=["Generate architecture summary"],
    )

    await generate_intentions_from_desires(stub_agent)

    stage2_run_calls = [
        call for call in stub_agent.run_calls if call["output_type"] is DetailedStepList
    ]
    stage2_prompt_for_second_intention = stage2_run_calls[1]["prompt"]
    assert "Collect repository metadata" in stage2_prompt_for_second_intention


@pytest.mark.asyncio
async def test_planning_skips_intention_when_already_covered(stub_agent) -> None:
    stub_agent.add_desire(
        desire_id="desire_1",
        description="Deliver report",
        status=DesireStatus.ACTIVE,
    )
    stub_agent.initial_intention_guidance = ["Collect data", "Collect data again"]

    _queue_stage2_with_judgement(
        stub_agent,
        step_descriptions=["Collect repository metadata"],
        reason="First plan is necessary.",
    )
    _queue_stage2_with_judgement(
        stub_agent,
        step_descriptions=["Collect repository metadata"],
        decision="skip",
        reason_category="already_planned",
        reason="Covered by previous intention.",
    )

    await generate_intentions_from_desires(stub_agent)

    assert len(stub_agent.intentions) == 1
    assert stub_agent.intentions[0].description == "Collect data"


@pytest.mark.asyncio
async def test_planning_deduplicates_steps_across_intentions(stub_agent) -> None:
    stub_agent.add_desire(
        desire_id="desire_1",
        description="Deliver report",
        status=DesireStatus.ACTIVE,
    )
    stub_agent.initial_intention_guidance = ["Collect data", "Analyze data"]

    _queue_stage2_with_judgement(
        stub_agent,
        step_descriptions=["Collect repository metadata"],
        reason="First plan is necessary.",
    )
    _queue_stage2_with_judgement(
        stub_agent,
        step_descriptions=["Collect repository metadata", "Summarize findings"],
        reason="Includes new work.",
    )

    await generate_intentions_from_desires(stub_agent)

    assert len(stub_agent.intentions) == 2
    assert len(stub_agent.intentions[1].steps) == 1
    assert stub_agent.intentions[1].steps[0].description == "Summarize findings"
