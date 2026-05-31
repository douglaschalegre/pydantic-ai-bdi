"""Centralized belief update helpers for BDI flows."""

import json
from datetime import datetime
from difflib import SequenceMatcher
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Dict, Iterable, Literal, Tuple, cast

from helper.util import bcolors
from bdi.errors import is_validation_output_error
from bdi.logging import log_states
from bdi.prompts import (
    build_belief_name_resolution_prompt,
    build_belief_update_resolution_prompt,
)
from bdi.schemas import BeliefNameResolutionDecision, BeliefUpdateDecision
from bdi.schemas.belief_schemas import BatchBeliefResolutionResult

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


def _stable_value_key(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, default=str)
    except TypeError:
        return repr(value)


def _deduplicate_step_beliefs(
    beliefs: Iterable[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    deduplicated: list[Dict[str, Any]] = []
    seen: Dict[tuple[str, str], int] = {}

    for belief_dict in beliefs:
        belief_name = _normalize_belief_name(str(belief_dict["name"]))
        belief_value = belief_dict["value"]
        belief_certainty = float(belief_dict.get("certainty", 0.8))
        key = (belief_name, _stable_value_key(belief_value))

        if key in seen:
            existing = deduplicated[seen[key]]
            existing["certainty"] = max(existing["certainty"], belief_certainty)
            continue

        seen[key] = len(deduplicated)
        deduplicated.append(
            {
                "name": belief_name,
                "value": belief_value,
                "certainty": belief_certainty,
            }
        )

    return deduplicated


_NAME_TOKEN_ALIASES = {
    "directories": "directory",
    "dirs": "directory",
    "dir": "directory",
    "repositories": "repository",
    "repo": "repository",
}


def _canonical_name_token(token: str) -> str:
    token = token.strip().lower()
    token = _NAME_TOKEN_ALIASES.get(token, token)
    if len(token) > 3 and token.endswith("s"):
        token = token[:-1]
    return token


def _belief_name_tokens(name: str) -> set[str]:
    return {
        _canonical_name_token(token)
        for token in name.replace("-", "_").split("_")
        if token
    }


def _is_potential_name_match(incoming_name: str, existing_name: str) -> bool:
    incoming_tokens = _belief_name_tokens(incoming_name)
    existing_tokens = _belief_name_tokens(existing_name)
    shared_tokens = incoming_tokens & existing_tokens

    if incoming_tokens and incoming_tokens == existing_tokens:
        return True
    if len(shared_tokens) >= 2:
        return True
    return SequenceMatcher(None, incoming_name, existing_name).ratio() >= 0.72


def _ambiguous_existing_names(agent: "BDI", incoming_name: str) -> list[str]:
    return [
        existing_name
        for existing_name in agent.beliefs.beliefs
        if existing_name != incoming_name
        and _is_potential_name_match(incoming_name, existing_name)
    ]


def _build_batch_belief_resolution_prompt(
    *,
    pending_beliefs: list[Dict[str, Any]],
    existing_beliefs: Dict[str, Any],
) -> str:
    incoming_beliefs = [
        {
            "incoming_index": belief["index"],
            "name": belief["name"],
            "value": belief["value"],
            "certainty": belief["certainty"],
            "source": belief["source"],
            "resolution_reason": belief["resolution_reason"],
            "candidate_existing_names": belief["candidate_existing_names"],
        }
        for belief in pending_beliefs
    ]

    return dedent(f"""
        Resolve this batch of incoming belief updates against the current belief state.

        Current beliefs (name -> value):
        {json.dumps(existing_beliefs, default=str, sort_keys=True)}

        Incoming beliefs needing resolution:
        {json.dumps(incoming_beliefs, default=str, sort_keys=True)}

        Rules:
        1. Return exactly one decision for each incoming belief by incoming_index.
        2. For ambiguous names, reuse an existing belief name only when it represents the same concept.
        3. For conflicting values, decide whether the incoming value should replace the existing value.
        4. If values are semantically equivalent, set should_update=false and keep the existing value.
        5. If creating a new belief, use the incoming normalized name as resolved_name.
        6. Certainty must be between 0.0 and 1.0.

        Return structured output with a decisions list. Each decision must include:
        - incoming_index
        - resolved_name
        - should_update
        - normalized_value
        - certainty
        - rationale
        """)


async def _llm_resolve_belief_updates_batch(
    agent: "BDI",
    pending_beliefs: list[Dict[str, Any]],
) -> Dict[int, tuple[str, bool, Any, float]]:
    prompt = _build_batch_belief_resolution_prompt(
        pending_beliefs=pending_beliefs,
        existing_beliefs=_current_belief_value_map(agent),
    )

    try:
        result = await agent.run(prompt, output_type=BatchBeliefResolutionResult)
        if not result or not result.output:
            return {}

        decisions: Dict[int, tuple[str, bool, Any, float]] = {}
        for decision in result.output.decisions:
            decisions[decision.incoming_index] = (
                _normalize_belief_name(decision.resolved_name),
                decision.should_update,
                decision.normalized_value,
                max(0.0, min(1.0, float(decision.certainty))),
            )
        return decisions
    except Exception as e:
        if agent.verbose and not is_validation_output_error(e):
            print(
                f"{bcolors.WARNING}  Batch belief resolution failed, using fallback: {e}{bcolors.ENDC}"
            )

    return {}


def _fallback_batch_decision(
    agent: "BDI", pending_belief: Dict[str, Any]
) -> tuple[str, bool, Any, float]:
    belief_name = pending_belief["name"]
    existing = agent.beliefs.get(belief_name)

    if existing and existing.value == pending_belief["value"]:
        should_update = pending_belief["certainty"] > existing.certainty
        return (
            belief_name,
            should_update,
            pending_belief["value"],
            pending_belief["certainty"],
        )

    if pending_belief["resolution_reason"] == "ambiguous_name":
        return belief_name, True, pending_belief["value"], pending_belief["certainty"]

    return belief_name, True, pending_belief["value"], pending_belief["certainty"]


def _apply_resolved_belief_update(
    agent: "BDI",
    *,
    belief_name: str,
    value_to_store: Any,
    certainty_to_store: float,
    source: str,
    should_update: bool,
) -> Tuple[str, Any, float, BeliefMutation]:
    if not should_update:
        existing = agent.beliefs.get(belief_name)
        if existing:
            return belief_name, existing.value, existing.certainty, "unchanged"
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
    stored = agent.beliefs.get(belief_name)
    if stored:
        return belief_name, stored.value, stored.certainty, mutation
    return belief_name, value_to_store, certainty_to_store, mutation


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
    applied_results: list[Tuple[str, Any, float, BeliefMutation]] = []
    pending_resolution: list[Dict[str, Any]] = []

    for index, belief_dict in enumerate(_deduplicate_step_beliefs(beliefs)):
        belief_name = belief_dict["name"]
        incoming_value = belief_dict["value"]
        incoming_certainty = belief_dict["certainty"]
        existing = agent.beliefs.get(belief_name)

        if existing and existing.value != incoming_value:
            pending_resolution.append(
                {
                    "index": index,
                    "name": belief_name,
                    "value": incoming_value,
                    "certainty": incoming_certainty,
                    "source": source,
                    "resolution_reason": "conflicting_value",
                    "candidate_existing_names": [belief_name],
                }
            )
            continue

        ambiguous_names = (
            [] if existing else _ambiguous_existing_names(agent, belief_name)
        )
        if ambiguous_names:
            pending_resolution.append(
                {
                    "index": index,
                    "name": belief_name,
                    "value": incoming_value,
                    "certainty": incoming_certainty,
                    "source": source,
                    "resolution_reason": "ambiguous_name",
                    "candidate_existing_names": ambiguous_names,
                }
            )
            continue

        applied_results.append(
            _apply_resolved_belief_update(
                agent,
                belief_name=belief_name,
                value_to_store=incoming_value,
                certainty_to_store=incoming_certainty,
                source=source,
                should_update=True,
            )
        )

    if pending_resolution:
        decisions = await _llm_resolve_belief_updates_batch(agent, pending_resolution)
        for pending_belief in pending_resolution:
            belief_name, should_update, value_to_store, certainty_to_store = (
                decisions.get(pending_belief["index"])
                or _fallback_batch_decision(agent, pending_belief)
            )
            applied_results.append(
                _apply_resolved_belief_update(
                    agent,
                    belief_name=belief_name,
                    value_to_store=value_to_store,
                    certainty_to_store=certainty_to_store,
                    source=source,
                    should_update=should_update,
                )
            )

    for belief_name, value_to_store, certainty_to_store, mutation in applied_results:
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
