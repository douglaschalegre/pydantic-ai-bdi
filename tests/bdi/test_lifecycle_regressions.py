import pytest

import bdi.cycle as cycle
import bdi.execution as execution
from bdi.logging import log_states
from bdi.schemas import (
    BeliefExtractionResult,
    DesireSatisfactionResult,
    DesireStatus,
    PlanStatus,
    StepAssessmentResult,
)
from bdi.schemas.belief_schemas import (
    BatchBeliefResolutionDecision,
    BatchBeliefResolutionResult,
)
from bdi.state_transitions import update_desire_status


@pytest.mark.asyncio
async def test_cycle_preserves_one_active_intention_through_write_and_verification(
    monkeypatch,
    stub_agent,
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_benchmark",
        description="Write the benchmark answer and verify it",
        status=DesireStatus.PENDING,
    )
    adoption_calls = 0

    async def adopt_write_verify_plan(agent):
        nonlocal adoption_calls
        adoption_calls += 1
        intention = agent.set_current_intention(
            desire_id=desire.id,
            step_descriptions=[
                "write benchmark implementation",
                "verify benchmark implementation",
            ],
        )
        intention.description = "Complete benchmark task"
        update_desire_status(agent, desire.id, DesireStatus.ACTIVE)

    async def fail_if_reconsideration_runs(_agent):
        raise AssertionError("successful Plan Step progress should not reconsider")

    monkeypatch.setattr(
        cycle, "generate_intentions_from_desires", adopt_write_verify_plan
    )
    monkeypatch.setattr(
        cycle, "reconsider_current_intention", fail_if_reconsideration_runs
    )

    stub_agent.queue_run_output("implementation written")
    stub_agent.queue_run_output(
        StepAssessmentResult(success=True, reason="write phase completed")
    )
    stub_agent.queue_run_output(
        BeliefExtractionResult(beliefs=[], explanation="no new beliefs")
    )

    first_result = await cycle.bdi_cycle(stub_agent)

    assert first_result == "executed"
    assert adoption_calls == 1
    assert desire.status is DesireStatus.ACTIVE
    assert len(stub_agent.intentions) == 1
    intention = stub_agent.intentions[0]
    assert intention.desire_id == desire.id
    assert intention.active_plan.status is PlanStatus.ACTIVE
    assert intention.active_plan.current_step_index == 1
    assert [
        history.step_description for history in intention.active_plan.step_history
    ] == ["write benchmark implementation"]

    stub_agent.queue_run_output("verification passed")
    stub_agent.queue_run_output(
        StepAssessmentResult(success=True, reason="verification phase completed")
    )
    stub_agent.queue_run_output(
        BeliefExtractionResult(beliefs=[], explanation="no new beliefs")
    )
    stub_agent.queue_run_output(
        DesireSatisfactionResult(satisfied=True, reason="write and verification passed")
    )

    second_result = await cycle.bdi_cycle(stub_agent)

    assert second_result == "terminal"
    assert adoption_calls == 1
    assert desire.status is DesireStatus.ACHIEVED
    assert len(stub_agent.intentions) == 0
    assert intention.active_plan.status is PlanStatus.COMPLETED
    assert intention.active_plan.current_step_index == 2
    assert [
        history.step_description for history in intention.active_plan.step_history
    ] == [
        "write benchmark implementation",
        "verify benchmark implementation",
    ]


@pytest.mark.asyncio
async def test_execute_intentions_batches_belief_resolution_from_step_extraction(
    stub_agent,
) -> None:
    desire = stub_agent.add_desire(
        desire_id="desire_beliefs",
        description="Update facts while executing",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id=desire.id,
        step_descriptions=["write result", "verify result"],
    )
    stub_agent.beliefs.upsert("repo_path", "/old/repo", "seed", certainty=0.8)
    stub_agent.beliefs.upsert("service_status", "offline", "seed", certainty=0.8)
    stub_agent.queue_run_output("result written in /tmp/repo and service is online")
    stub_agent.queue_run_output(StepAssessmentResult(success=True, reason="progress"))
    stub_agent.queue_run_output(
        BeliefExtractionResult(
            beliefs=[
                {"name": "repository_path", "value": "/tmp/repo", "certainty": 0.95},
                {"name": "service_status", "value": "online", "certainty": 0.9},
            ],
            explanation="extracted execution facts",
        )
    )
    stub_agent.queue_run_output(
        BatchBeliefResolutionResult(
            decisions=[
                BatchBeliefResolutionDecision(
                    incoming_index=0,
                    resolved_name="repo_path",
                    should_update=True,
                    normalized_value="/tmp/repo",
                    certainty=0.95,
                    rationale="repository_path is the same concept as repo_path",
                ),
                BatchBeliefResolutionDecision(
                    incoming_index=1,
                    resolved_name="service_status",
                    should_update=True,
                    normalized_value="online",
                    certainty=0.9,
                    rationale="latest execution observed the service online",
                ),
            ]
        )
    )

    result = await execution.execute_intentions(stub_agent)

    assert result == {"hitl_modified_plan": False, "hitl_updated_beliefs": False}
    assert desire.status is DesireStatus.ACTIVE
    assert len(stub_agent.intentions) == 1
    assert stub_agent.intentions[0] is intention
    assert intention.active_plan.current_step_index == 1
    assert stub_agent.beliefs.get("repo_path").value == "/tmp/repo"
    assert stub_agent.beliefs.get("repository_path") is None
    assert stub_agent.beliefs.get("service_status").value == "online"
    assert [call["output_type"] for call in stub_agent.run_calls] == [
        None,
        StepAssessmentResult,
        BeliefExtractionResult,
        BatchBeliefResolutionResult,
    ]
    assert (
        intention.active_plan.step_history[0].beliefs_updated["repo_path"]["value"]
        == "/tmp/repo"
    )
    assert (
        intention.active_plan.step_history[0].beliefs_updated["service_status"]["value"]
        == "online"
    )


def test_log_states_exposes_desire_intention_plan_and_plan_step(
    capsys,
    stub_agent,
) -> None:
    stub_agent.add_desire(
        desire_id="desire_log",
        description="Ship the lifecycle regression",
        status=DesireStatus.ACTIVE,
    )
    intention = stub_agent.set_current_intention(
        desire_id="desire_log",
        step_descriptions=[
            "inspect lifecycle",
            "write lifecycle regression",
            "verify lifecycle regression",
        ],
        current_step=1,
    )
    intention.description = "Ship lifecycle regression"

    log_states(
        stub_agent,
        ["desires", "intentions"],
        message="Lifecycle state snapshot",
    )

    output = capsys.readouterr().out
    assert "Lifecycle state snapshot" in output
    assert "Desires: 1 items" in output
    assert "Desire 'desire_log'" in output
    assert "Desire 'desire_log' active" in output
    assert "Intention 'Ship lifecycle regression'" in output
    assert "Plan active" in output
    assert "Plan Step 2/3" in output
    assert "write lifecycle regression" in output
