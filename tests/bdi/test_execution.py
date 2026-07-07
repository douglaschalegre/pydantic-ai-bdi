import pytest
from types import SimpleNamespace
from typing import Any, cast

import bdi.execution as execution
from bdi.schemas import (
    BeliefExtractionResult,
    DesireSatisfactionResult,
    DesireStatus,
    ExtractedBelief,
    PlanStatus,
    PlanStep,
    StepAssessmentResult,
)


@pytest.mark.asyncio
async def test_execute_intentions_no_intentions_returns_default(stub_agent) -> None:
    result = await execution.execute_intentions(stub_agent)

    assert result == {"hitl_modified_plan": False, "hitl_updated_beliefs": False}


@pytest.mark.asyncio
async def test_execute_intentions_completed_intention_finalizes_desire(
    stub_agent,
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_done",
        description="Already complete",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["step one"],
    )
    plan = intention.active_plan
    plan.current_step_index = len(plan.steps)
    stub_agent.queue_run_output(
        DesireSatisfactionResult(satisfied=True, reason="Already complete")
    )

    result = await execution.execute_intentions(stub_agent)

    assert result == {"hitl_modified_plan": False, "hitl_updated_beliefs": False}
    assert desire.status is DesireStatus.ACHIEVED
    assert len(stub_agent.intentions) == 0
    assert plan.status is PlanStatus.COMPLETED


@pytest.mark.asyncio
async def test_execute_intentions_exception_preserves_commitment_for_reconsideration(
    monkeypatch, stub_agent
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_exception",
        description="Exception path",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["step one"],
    )

    async def raising_run(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(stub_agent, "run", raising_run)

    result = await execution.execute_intentions(stub_agent)

    assert result == {"hitl_modified_plan": False, "hitl_updated_beliefs": False}
    assert desire.status is DesireStatus.ACTIVE
    assert len(stub_agent.intentions) == 1
    assert stub_agent.intentions[0] is intention
    assert intention.active_plan.status is PlanStatus.FAILED
    assert len(intention.active_plan.step_history) == 1
    assert intention.active_plan.step_history[0].success is False
    assert intention.active_plan.step_history[0].result == "Exception: boom"


@pytest.mark.asyncio
async def test_execute_intentions_success_completes_single_step(
    monkeypatch, stub_agent
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_success",
        description="Happy path",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["step one"],
    )

    async def always_success(*_args, **_kwargs):
        return True

    monkeypatch.setattr(
        execution,
        "analyze_step_outcome_and_update_beliefs",
        always_success,
    )
    stub_agent.queue_run_output("done")
    stub_agent.queue_run_output(
        DesireSatisfactionResult(satisfied=True, reason="Step completed desire")
    )

    result = await execution.execute_intentions(stub_agent)

    assert result == {"hitl_modified_plan": False, "hitl_updated_beliefs": False}
    assert desire.status is DesireStatus.ACHIEVED
    assert len(stub_agent.intentions) == 0
    assert intention.active_plan.status is PlanStatus.COMPLETED
    assert intention.active_plan.current_step_index == 1
    assert len(intention.active_plan.step_history) == 1
    assert intention.active_plan.step_history[0].success is True
    assert intention.active_plan.step_history[0].result == "done"


def test_extract_latest_tool_result_content_prefers_tool_payload() -> None:
    step_result = SimpleNamespace(
        all_messages=lambda: [
            SimpleNamespace(
                parts=[
                    SimpleNamespace(
                        tool_name="run_in_tac",
                        args={"command": "cat /instruction/task.md"},
                    ),
                    SimpleNamespace(
                        tool_call_id="call_1", content="raw instruction content"
                    ),
                ]
            )
        ]
    )

    extracted = execution._extract_latest_tool_result_content(cast(Any, step_result))
    assert extracted == "raw instruction content"


@pytest.mark.asyncio
async def test_analyze_step_outcome_without_result_returns_false(stub_agent) -> None:
    succeeded = await execution.analyze_step_outcome_and_update_beliefs(
        stub_agent,
        PlanStep(description="step without result"),
        None,
    )

    assert succeeded is False
    assert stub_agent.run_calls == []


@pytest.mark.asyncio
async def test_analyze_step_outcome_non_tool_assessment_exception_falls_back_to_failure(
    monkeypatch,
    stub_agent,
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_assessment_error",
        description="Assessment fallback",
        status=DesireStatus.ACTIVE,
    )
    stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["describe outcome"],
    )

    async def run_with_assessment_error(_prompt, *, output_type=None):
        if output_type is StepAssessmentResult:
            raise RuntimeError("assessment failed")
        if output_type is BeliefExtractionResult:
            return SimpleNamespace(
                output=BeliefExtractionResult(beliefs=[], explanation="nothing new")
            )
        raise AssertionError(f"unexpected output_type: {output_type}")

    monkeypatch.setattr(stub_agent, "run", run_with_assessment_error)

    succeeded = await execution.analyze_step_outcome_and_update_beliefs(
        stub_agent,
        PlanStep(description="describe outcome"),
        SimpleNamespace(output="ambiguous result"),
    )

    assert succeeded is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_output", "expected_success"),
    [
        ("x" * 80, True),
        ("error: file not found", False),
    ],
)
async def test_analyze_step_outcome_tool_assessment_exception_uses_output_fallback(
    monkeypatch,
    stub_agent,
    tool_output,
    expected_success,
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_tool_fallback",
        description="Tool fallback",
        status=DesireStatus.ACTIVE,
    )
    stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["call tool"],
    )

    async def run_with_assessment_error(_prompt, *, output_type=None):
        if output_type is StepAssessmentResult:
            raise RuntimeError("assessment failed")
        if output_type is BeliefExtractionResult:
            return SimpleNamespace(
                output=BeliefExtractionResult(beliefs=[], explanation="nothing new")
            )
        raise AssertionError(f"unexpected output_type: {output_type}")

    monkeypatch.setattr(stub_agent, "run", run_with_assessment_error)

    succeeded = await execution.analyze_step_outcome_and_update_beliefs(
        stub_agent,
        PlanStep(description="call tool", is_tool_call=True, tool_name="read_file"),
        SimpleNamespace(output=tool_output),
    )

    assert succeeded is expected_success


@pytest.mark.asyncio
async def test_analyze_step_outcome_extends_optional_belief_output(
    stub_agent,
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_belief_output",
        description="Extract beliefs",
        status=DesireStatus.ACTIVE,
    )
    stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["inspect repo"],
    )
    stub_agent.queue_run_output(
        StepAssessmentResult(success=True, reason="inspection succeeded")
    )
    stub_agent.queue_run_output(
        BeliefExtractionResult(
            beliefs=[
                ExtractedBelief(name="repo_path", value="/tmp/repo", certainty=0.9)
            ],
            explanation="repo path found",
        )
    )
    extracted_beliefs = []

    succeeded = await execution.analyze_step_outcome_and_update_beliefs(
        stub_agent,
        PlanStep(description="inspect repo"),
        SimpleNamespace(output="repo is /tmp/repo"),
        extracted_beliefs_out=extracted_beliefs,
    )

    assert succeeded is True
    assert extracted_beliefs == [
        {"name": "repo_path", "value": "/tmp/repo", "certainty": 0.9}
    ]
    assert stub_agent.beliefs.get("repo_path").value == "/tmp/repo"


def test_build_retry_context_formats_failure_history() -> None:
    empty_context = execution.StepRetryContext()
    assert execution._build_retry_context(empty_context) == ""

    retry_context = execution.StepRetryContext(attempt_number=1)
    retry_context.record_failure(
        result_output="file missing",
        beliefs_extracted=[
            {"name": "repo_path", "value": "/tmp/repo", "certainty": 0.8}
        ],
    )

    formatted = execution._build_retry_context(retry_context)

    assert "PREVIOUS ATTEMPT FAILURES" in formatted
    assert "Attempt 2: file missing" in formatted
    assert "Beliefs learned:" in formatted
    assert "repo_path" in formatted


@pytest.mark.asyncio
async def test_run_step_attempt_tool_prefers_raw_tool_result(
    monkeypatch,
    stub_agent,
) -> None:
    step_result = SimpleNamespace(
        output="model summary",
        all_messages=lambda: [
            SimpleNamespace(
                parts=[SimpleNamespace(tool_call_id="call_1", content=b"raw bytes")]
            )
        ],
    )

    async def run_tool_prompt(_prompt):
        return step_result

    monkeypatch.setattr(stub_agent, "run", run_tool_prompt)

    result = await execution._run_step_attempt(
        stub_agent,
        PlanStep(
            description="read instructions",
            is_tool_call=True,
            tool_name="read_file",
            tool_params={"path": "/tmp/task.md"},
        ),
        execution.StepRetryContext(),
    )

    assert result.output == "raw bytes"
