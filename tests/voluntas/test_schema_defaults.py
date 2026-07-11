from voluntas.schemas import (
    BeliefExtractionResult,
    ExtractedBelief,
    Plan,
    PlanStep,
    PlanStepHistory,
)


def test_plan_step_history_isolated_per_instance() -> None:
    first = Plan(steps=[PlanStep(description="step a")])
    second = Plan(steps=[PlanStep(description="step b")])

    first.step_history.append(
        PlanStepHistory(
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
