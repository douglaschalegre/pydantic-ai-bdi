"""Centralized belief update helpers for BDI flows."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Iterable, Literal, Tuple, cast

from helper.util import bcolors
from bdi.errors import is_validation_output_error
from bdi.logging import log_states
from bdi.prompts import (
    build_belief_name_resolution_prompt,
    build_belief_update_resolution_prompt,
)
from bdi.schemas import BeliefNameResolutionDecision, BeliefUpdateDecision

if TYPE_CHECKING:
    from bdi.agent import BDI
    from bdi.schemas import Belief, ExtractedBelief


BeliefMutation = Literal["created", "updated", "unchanged"]
BeliefStats = Dict[BeliefMutation, int]
_MUTATION_MARKERS: Dict[BeliefMutation, str] = {
    "created": "+",
    "updated": "~",
    "unchanged": "=",
}


def _normalize_belief_name(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def _current_belief_value_map(agent: "BDI") -> Dict[str, Any]:
    return {name: belief.value for name, belief in agent.beliefs.beliefs.items()}


def _empty_stats() -> BeliefStats:
    return {"created": 0, "updated": 0, "unchanged": 0}


def _mutation_marker(mutation: BeliefMutation) -> str:
    return _MUTATION_MARKERS[mutation]


async def _llm_resolve_belief_name(
    agent: "BDI",
    *,
    incoming_name: str,
    incoming_value: Any,
) -> str:
    if not agent.beliefs.beliefs:
        return incoming_name

    prompt = build_belief_name_resolution_prompt(
        incoming_name=incoming_name,
        incoming_value=incoming_value,
        existing_beliefs=_current_belief_value_map(agent),
    )

    try:
        result = await agent.run(prompt, output_type=BeliefNameResolutionDecision)
        if result and result.output and result.output.resolved_name:
            return _normalize_belief_name(result.output.resolved_name)
    except Exception as e:
        if agent.verbose and not is_validation_output_error(e):
            print(
                f"{bcolors.WARNING}  Belief name resolution failed for '{incoming_name}', using incoming name: {e}{bcolors.ENDC}"
            )

    return incoming_name


async def _llm_evaluate_belief_update(
    agent: "BDI",
    *,
    belief_name: str,
    existing: "Belief",
    incoming_value: Any,
    incoming_certainty: float,
    incoming_source: str,
) -> Tuple[bool, Any, float]:
    prompt = build_belief_update_resolution_prompt(
        belief_name=belief_name,
        existing_value=existing.value,
        existing_certainty=existing.certainty,
        incoming_value=incoming_value,
        incoming_certainty=incoming_certainty,
        incoming_source=incoming_source,
    )

    try:
        decision_result = await agent.run(prompt, output_type=BeliefUpdateDecision)
        if decision_result and decision_result.output:
            decision = decision_result.output
            certainty = max(0.0, min(1.0, float(decision.certainty)))
            return decision.should_update, decision.normalized_value, certainty
    except Exception as e:
        if agent.verbose and not is_validation_output_error(e):
            print(
                f"{bcolors.WARNING}  Belief update evaluation failed for '{belief_name}', using fallback: {e}{bcolors.ENDC}"
            )

    if existing.value == incoming_value and incoming_certainty <= existing.certainty:
        return False, existing.value, existing.certainty
    return True, incoming_value, incoming_certainty


async def _evaluate_and_apply_belief_update(
    agent: "BDI",
    *,
    belief_name: str,
    incoming_value: Any,
    incoming_certainty: float,
    source: str,
) -> Tuple[str, Any, float, BeliefMutation]:
    existing = agent.beliefs.get(belief_name)
    should_update = True
    value_to_store: Any = incoming_value
    certainty_to_store = incoming_certainty

    if existing:
        should_update, value_to_store, certainty_to_store = (
            await _llm_evaluate_belief_update(
                agent,
                belief_name=belief_name,
                existing=existing,
                incoming_value=incoming_value,
                incoming_certainty=incoming_certainty,
                incoming_source=source,
            )
        )

    if not should_update:
        return belief_name, value_to_store, certainty_to_store, "unchanged"

    mutation = cast(
        BeliefMutation,
        agent.beliefs.upsert(
            name=belief_name,
            value=value_to_store,
            source=source,
            certainty=certainty_to_store,
        ),
    )
    return belief_name, value_to_store, certainty_to_store, mutation


async def update_beliefs_from_desire_extraction(
    agent: "BDI", beliefs: Iterable["ExtractedBelief"]
) -> BeliefStats:
    """Apply beliefs extracted from initial desire descriptions."""
    stats = _empty_stats()

    for belief in beliefs:
        _, _, _, mutation = await _evaluate_and_apply_belief_update(
            agent,
            belief_name=await _llm_resolve_belief_name(
                agent,
                incoming_name=_normalize_belief_name(belief.name),
                incoming_value=belief.value,
            ),
            incoming_value=belief.value,
            incoming_certainty=belief.certainty,
            source="desire_description",
        )
        stats[mutation] += 1

    return stats


async def update_beliefs_from_step_extraction(
    agent: "BDI", beliefs: Iterable[Dict[str, Any]], source: str
) -> BeliefStats:
    """Apply beliefs extracted from a step result."""
    stats = _empty_stats()

    for belief_dict in beliefs:
        belief_name, value_to_store, certainty_to_store, mutation = (
            await _evaluate_and_apply_belief_update(
                agent,
                belief_name=await _llm_resolve_belief_name(
                    agent,
                    incoming_name=_normalize_belief_name(str(belief_dict["name"])),
                    incoming_value=belief_dict["value"],
                ),
                incoming_value=belief_dict["value"],
                incoming_certainty=belief_dict["certainty"],
                source=source,
            )
        )

        stats[mutation] += 1
        if agent.verbose:
            print(
                f"{bcolors.BELIEF}    {_mutation_marker(mutation)} {belief_name}: {value_to_store} (Certainty: {certainty_to_store:.2f}) [{mutation}]{bcolors.ENDC}"
            )

    return stats


async def update_beliefs_from_hitl_guidance(
    agent: "BDI", beliefs_to_update: Dict[str, Dict[str, Any]]
) -> bool:
    """Apply beliefs provided through human-in-the-loop guidance."""
    beliefs_updated = False
    stats = _empty_stats()

    for name, belief_data_dict in beliefs_to_update.items():
        incoming_name = _normalize_belief_name(name)
        incoming_value = belief_data_dict.get("value")
        belief_name = await _llm_resolve_belief_name(
            agent,
            incoming_name=incoming_name,
            incoming_value=incoming_value,
        )
        belief_data_dict.setdefault("name", belief_name)
        belief_data_dict.setdefault("source", "human_guidance")
        belief_data_dict.setdefault("certainty", 1.0)
        belief_data_dict.setdefault("timestamp", datetime.now().timestamp())

        try:
            belief_name, value_to_store, _, mutation = (
                await _evaluate_and_apply_belief_update(
                    agent,
                    belief_name=belief_name,
                    incoming_value=belief_data_dict["value"],
                    incoming_certainty=belief_data_dict["certainty"],
                    source=belief_data_dict["source"],
                )
            )

            stats[mutation] += 1
            beliefs_updated = beliefs_updated or mutation in {"created", "updated"}
            if agent.verbose:
                print(
                    f"{bcolors.BELIEF}    {_mutation_marker(mutation)} {belief_name}: {value_to_store} (Source: human_guidance) [{mutation}]{bcolors.ENDC}"
                )
        except KeyError as e:
            print(
                f"{bcolors.FAIL}  Failed to update belief '{belief_name}' due to missing data: {e}{bcolors.ENDC}"
            )
        except Exception as e:
            print(
                f"{bcolors.FAIL}  Failed to update belief '{belief_name}': {e}{bcolors.ENDC}"
            )

    if beliefs_updated:
        log_states(agent, ["beliefs"], message="Beliefs updated from HITL guidance.")
    elif agent.verbose and beliefs_to_update:
        print(
            f"{bcolors.SYSTEM}  HITL beliefs unchanged ({stats['unchanged']} duplicate entries acknowledged).{bcolors.ENDC}"
        )

    return beliefs_updated


__all__ = [
    "update_beliefs_from_desire_extraction",
    "update_beliefs_from_hitl_guidance",
    "update_beliefs_from_step_extraction",
]
