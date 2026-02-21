from bdi.schemas import (
    BeliefExtractionResult,
    ExtractedBelief,
    Intention,
    IntentionStep,
    StepHistory,
)


def test_intention_step_history_isolated_per_instance() -> None:
    first = Intention(desire_id="desire_a", steps=[IntentionStep(description="step a")])
    second = Intention(
        desire_id="desire_b", steps=[IntentionStep(description="step b")]
    )

    first.step_history.append(
        StepHistory(
            step_description="step a",
            step_number=0,
            result="ok",
            success=True,
            timestamp=0.0,
            beliefs_updated={},
        )
    )

    assert first.step_history is not second.step_history
    assert len(first.step_history) == 1
    assert second.step_history == []


def test_belief_extraction_result_beliefs_isolated_per_instance() -> None:
    first = BeliefExtractionResult(explanation="first")
    second = BeliefExtractionResult(explanation="second")

    first.beliefs.append(
        ExtractedBelief(name="repo_path", value="/tmp/repo", certainty=1.0)
    )

    assert first.beliefs is not second.beliefs
    assert len(first.beliefs) == 1
    assert second.beliefs == []
