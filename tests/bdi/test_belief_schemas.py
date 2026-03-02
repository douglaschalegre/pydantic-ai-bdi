from bdi.schemas import BeliefUpdateDecision


def test_belief_update_decision_schema_has_typed_normalized_value() -> None:
    schema = BeliefUpdateDecision.model_json_schema()
    normalized_value = schema["properties"]["normalized_value"]

    assert normalized_value.get("type") == "string"
