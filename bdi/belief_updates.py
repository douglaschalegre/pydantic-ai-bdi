"""Centralized belief update helpers for BDI flows."""

from typing import TYPE_CHECKING, Any, Dict, Iterable
from datetime import datetime

from helper.util import bcolors
from bdi.logging import log_states

if TYPE_CHECKING:
    from bdi.agent import BDI
    from bdi.schemas import ExtractedBelief


def update_beliefs_from_desire_extraction(
    agent: "BDI", beliefs: Iterable["ExtractedBelief"]
) -> int:
    """Apply beliefs extracted from initial desire descriptions.

    Returns:
        Number of beliefs applied.
    """
    applied = 0
    for belief in beliefs:
        agent.beliefs.update(
            name=belief.name,
            value=belief.value,
            source="desire_description",
            certainty=belief.certainty,
        )
        applied += 1
    return applied


def update_beliefs_from_step_extraction(
    agent: "BDI", beliefs: Iterable[Dict[str, Any]], source: str
) -> int:
    """Apply beliefs extracted from a step result.

    Returns:
        Number of beliefs applied.
    """
    applied = 0
    for belief_dict in beliefs:
        agent.beliefs.update(
            name=belief_dict["name"],
            value=belief_dict["value"],
            source=source,
            certainty=belief_dict["certainty"],
        )
        if agent.verbose:
            print(
                f"{bcolors.BELIEF}    + {belief_dict['name']}: {belief_dict['value']} (Certainty: {belief_dict['certainty']:.2f}){bcolors.ENDC}"
            )
        applied += 1
    return applied


def update_beliefs_from_hitl_guidance(
    agent: "BDI", beliefs_to_update: Dict[str, Dict[str, Any]]
) -> bool:
    """Apply beliefs provided through human-in-the-loop guidance.

    Returns:
        True when at least one belief is updated.
    """
    beliefs_updated = False

    for name, belief_data_dict in beliefs_to_update.items():
        belief_data_dict.setdefault("name", name)
        belief_data_dict.setdefault("source", "human_guidance")
        belief_data_dict.setdefault("certainty", 1.0)
        belief_data_dict.setdefault("timestamp", datetime.now().timestamp())
        try:
            agent.beliefs.update(
                name=name,
                value=belief_data_dict["value"],
                source=belief_data_dict["source"],
                certainty=belief_data_dict["certainty"],
            )
            if agent.verbose:
                print(
                    f"{bcolors.BELIEF}    + {name}: {belief_data_dict['value']} (Source: human_guidance){bcolors.ENDC}"
                )
            beliefs_updated = True
        except KeyError as e:
            print(
                f"{bcolors.FAIL}  Failed to update belief '{name}' due to missing data: {e}{bcolors.ENDC}"
            )
        except Exception as e:
            print(
                f"{bcolors.FAIL}  Failed to update belief '{name}': {e}{bcolors.ENDC}"
            )

    if beliefs_updated:
        log_states(agent, ["beliefs"], message="Beliefs updated from HITL guidance.")

    return beliefs_updated


__all__ = [
    "update_beliefs_from_desire_extraction",
    "update_beliefs_from_hitl_guidance",
    "update_beliefs_from_step_extraction",
]
