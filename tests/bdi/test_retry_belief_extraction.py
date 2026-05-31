from types import SimpleNamespace

import pytest

import bdi.execution as execution
from bdi.schemas import DesireStatus, StepAssessmentResult


@pytest.mark.asyncio
async def test_failed_step_retry_reuses_analysis_extracted_beliefs(
    monkeypatch, stub_agent
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_retry", description="Retry test", status=DesireStatus.ACTIVE
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id, step_descriptions=["step one"]
    )
    extracted = [{"name": "failure_reason", "value": "missing file", "certainty": 0.9}]
    extraction_calls = 0

    async def failed_step_attempt(*_args, **_kwargs):
        return SimpleNamespace(output="failed because file is missing")

    async def extract_once_per_analysis(*_args, **_kwargs):
        nonlocal extraction_calls
        extraction_calls += 1
        return list(extracted)

    monkeypatch.setattr(execution, "_run_step_attempt", failed_step_attempt)
    monkeypatch.setattr(
        execution, "extract_relevant_beliefs_from_result", extract_once_per_analysis
    )
    for _ in range(execution.MAX_STEP_RETRIES + 1):
        stub_agent.queue_run_output(
            StepAssessmentResult(success=False, reason="Still failed")
        )

    step_result, step_succeeded, retry_ctx, early_return = (
        await execution._run_step_with_retries(
            stub_agent, intention, intention.steps[0]
        )
    )

    assert step_result is not None
    assert step_succeeded is False
    assert early_return is None
    assert extraction_calls == len(retry_ctx.failure_history)
    assert retry_ctx.failure_history
    assert all(failure["beliefs"] == extracted for failure in retry_ctx.failure_history)
