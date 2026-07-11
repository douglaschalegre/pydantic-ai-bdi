import pytest

from voluntas.belief_updates import update_beliefs_from_step_extraction
from voluntas.schemas.belief_schemas import (
    BatchBeliefResolutionDecision,
    BatchBeliefResolutionResult,
)


@pytest.mark.asyncio
async def test_step_beliefs_upsert_normalized_names_without_llm(stub_agent) -> None:
    stub_agent.beliefs.upsert(
        name="project_name", value="voluntas", source="seed", certainty=1.0
    )

    stats = await update_beliefs_from_step_extraction(
        stub_agent,
        [{"name": "Repo Path", "value": "/tmp/repo", "certainty": 0.9}],
        source="step_1",
    )

    belief = stub_agent.beliefs.get("repo_path")
    assert stats == {"created": 1, "updated": 0, "unchanged": 0}
    assert belief is not None
    assert belief.value == "/tmp/repo"
    assert stub_agent.run_calls == []


@pytest.mark.asyncio
async def test_step_beliefs_deduplicate_repeated_facts_before_update(
    stub_agent,
) -> None:
    stats = await update_beliefs_from_step_extraction(
        stub_agent,
        [
            {"name": "repo_path", "value": "/tmp/repo", "certainty": 0.7},
            {"name": "Repo Path", "value": "/tmp/repo", "certainty": 0.95},
        ],
        source="step_1",
    )

    belief = stub_agent.beliefs.get("repo_path")
    assert stats == {"created": 1, "updated": 0, "unchanged": 0}
    assert belief is not None
    assert belief.certainty == 0.95
    assert stub_agent.run_calls == []


@pytest.mark.asyncio
async def test_step_beliefs_resolve_ambiguous_names_in_one_batch(stub_agent) -> None:
    stub_agent.beliefs.upsert(
        name="repo_path", value="/old/repo", source="seed", certainty=0.8
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
                )
            ]
        )
    )

    stats = await update_beliefs_from_step_extraction(
        stub_agent,
        [{"name": "repository_path", "value": "/tmp/repo", "certainty": 0.95}],
        source="step_1",
    )

    assert stats == {"created": 0, "updated": 1, "unchanged": 0}
    assert stub_agent.beliefs.get("repo_path").value == "/tmp/repo"
    assert stub_agent.beliefs.get("repository_path") is None
    assert len(stub_agent.run_calls) == 1
    assert stub_agent.run_calls[0]["output_type"] is BatchBeliefResolutionResult


@pytest.mark.asyncio
async def test_step_beliefs_resolve_conflicting_values_in_one_batch(
    stub_agent,
) -> None:
    stub_agent.beliefs.upsert(
        name="service_status", value="offline", source="seed", certainty=0.8
    )
    stub_agent.beliefs.upsert(
        name="api_status", value="down", source="seed", certainty=0.8
    )
    stub_agent.queue_run_output(
        BatchBeliefResolutionResult(
            decisions=[
                BatchBeliefResolutionDecision(
                    incoming_index=0,
                    resolved_name="service_status",
                    should_update=True,
                    normalized_value="online",
                    certainty=0.9,
                    rationale="The newer check found the service online",
                ),
                BatchBeliefResolutionDecision(
                    incoming_index=1,
                    resolved_name="api_status",
                    should_update=False,
                    normalized_value="down",
                    certainty=0.8,
                    rationale="The incoming value is less reliable",
                ),
            ]
        )
    )

    stats = await update_beliefs_from_step_extraction(
        stub_agent,
        [
            {"name": "service_status", "value": "online", "certainty": 0.9},
            {"name": "api_status", "value": "degraded", "certainty": 0.6},
        ],
        source="step_1",
    )

    assert stats == {"created": 0, "updated": 1, "unchanged": 1}
    assert stub_agent.beliefs.get("service_status").value == "online"
    assert stub_agent.beliefs.get("api_status").value == "down"
    assert len(stub_agent.run_calls) == 1
    assert stub_agent.run_calls[0]["output_type"] is BatchBeliefResolutionResult
