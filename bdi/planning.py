"""Planning and deliberation for the BDI agent.

This module converts active desires into high-level intentions. Each generated
intention is executed as one descriptive step, letting the execution agent use
tools and reconcile outcomes without pre-expanding a brittle detailed plan.
"""

from collections import deque
import re
from typing import TYPE_CHECKING, List

from helper.util import bcolors
from bdi.schemas import (
    Intention,
    HighLevelIntention,
    HighLevelIntentionList,
    DesireStatus,
    IntentionStep,
)
from bdi.logging import log_states
from bdi.prompts import build_planning_stage1_prompt
from bdi.state_transitions import update_desire_status

if TYPE_CHECKING:
    from bdi.agent import BDI


_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_text(value: str) -> str:
    """Normalize text for stable duplicate detection."""
    return _WHITESPACE_RE.sub(" ", value.strip().lower())


def _intention_fingerprint(hl_intention: HighLevelIntention) -> str:
    """Build a fingerprint for high-level intention deduplication."""
    return f"{hl_intention.desire_id}|{_normalize_text(hl_intention.description)}"


def _deduplicate_high_level_intentions(
    high_level_intentions: List[HighLevelIntention],
    *,
    verbose: bool,
) -> List[HighLevelIntention]:
    """Return high-level intentions with duplicate entries removed."""
    unique_high_level_intentions: List[HighLevelIntention] = []
    seen_fingerprints: set[str] = set()

    for high_level_intention in high_level_intentions:
        fingerprint = _intention_fingerprint(high_level_intention)
        if fingerprint in seen_fingerprints:
            if verbose:
                print(
                    f"{bcolors.WARNING}  Skipping duplicate high-level intention: {high_level_intention.description}{bcolors.ENDC}"
                )
            continue

        seen_fingerprints.add(fingerprint)
        unique_high_level_intentions.append(high_level_intention)

    return unique_high_level_intentions


def _build_intention(high_level_intention: HighLevelIntention) -> Intention:
    """Represent a high-level intention as one executable descriptive step."""
    return Intention(
        desire_id=high_level_intention.desire_id,
        description=high_level_intention.description,
        steps=[IntentionStep(description=high_level_intention.description)],
    )


async def generate_intentions_from_desires(agent: "BDI") -> None:
    """Convert desires into high-level executable intentions.

    The planner now performs only one planning pass. Detailed-step expansion is
    intentionally omitted to avoid over-granular plans and excess replanning
    cycles.

    Args:
        agent: The BDI agent instance
    """
    if not agent.desires:
        print(f"{bcolors.SYSTEM}No desires to generate intentions from.{bcolors.ENDC}")
        return
    if agent.intentions:
        print(
            f"{bcolors.SYSTEM}Intentions already exist, skipping generation.{bcolors.ENDC}"
        )
        return

    active_desires = [
        d
        for d in agent.desires
        if d.status in [DesireStatus.PENDING, DesireStatus.ACTIVE]
    ]
    if not active_desires:
        print(f"{bcolors.SYSTEM}No active or pending desires to plan for.{bcolors.ENDC}")
        return

    if agent.verbose:
        print(
            f"{bcolors.SYSTEM}Starting single-stage intention generation...{bcolors.ENDC}"
        )

    # --- Context Gathering ---
    desires_text = "\n".join(
        [f"- ID: {d.id}, Description: {d.description}" for d in active_desires]
    )
    beliefs_text = (
        "\n".join(
            [
                f"- {name}: {belief.value} (Source: {belief.source}, Certainty: {belief.certainty:.2f})"
                for name, belief in agent.beliefs.beliefs.items()
            ]
        )
        if agent.beliefs.beliefs
        else "No current beliefs."
    )

    # --- Generate High-Level Intentions ---
    # Check if explicit intentions were provided by the user
    # If so, use them directly instead of generating via LLM
    high_level_intentions: List[HighLevelIntention] = []

    use_explicit_intentions = bool(agent.initial_intention_guidance) and not getattr(
        agent,
        "_initial_intention_guidance_consumed",
        False,
    )

    if use_explicit_intentions:
        agent._initial_intention_guidance_consumed = True
        # User provided explicit intentions - use them directly
        # Associate all intentions with the first active/pending desire
        # (In most cases, explicit intentions relate to a single primary desire)
        primary_desire_id = (
            active_desires[0].id if active_desires else agent.desires[0].id
        )

        print(
            f"{bcolors.SYSTEM}Using {len(agent.initial_intention_guidance)} explicit intentions provided by user (skipping planning LLM).{bcolors.ENDC}"
        )

        for intention_desc in agent.initial_intention_guidance:
            high_level_intentions.append(
                HighLevelIntention(
                    desire_id=primary_desire_id,
                    description=intention_desc,
                )
            )
            if agent.verbose:
                print(f"{bcolors.INTENTION}  - {intention_desc}{bcolors.ENDC}")
    else:
        # No explicit intentions - generate high-level intentions via LLM.
        if agent.verbose:
            print(
                f"{bcolors.SYSTEM}Generating high-level intentions...{bcolors.ENDC}"
            )
        intention_guidance_text = (
            "\n".join(f"- {item}" for item in agent.initial_intention_guidance)
            if agent.initial_intention_guidance
            else None
        )
        prompt_stage1 = build_planning_stage1_prompt(
            desires_text,
            beliefs_text,
            intention_guidance_text,
        )
        try:
            stage1_result = await agent.run(
                prompt_stage1, output_type=HighLevelIntentionList
            )
            if (
                not stage1_result
                or not stage1_result.output
                or not stage1_result.output.intentions
            ):
                print(
                    f"{bcolors.FAIL}Intention generation failed: No high-level intentions generated.{bcolors.ENDC}"
                )
                return
            high_level_intentions = stage1_result.output.intentions
            print(
                f"{bcolors.SYSTEM}Generated {len(high_level_intentions)} high-level intentions.{bcolors.ENDC}"
            )

        except Exception as e:
            print(
                f"{bcolors.FAIL}Intention generation failed: Error during LLM call: {e}{bcolors.ENDC}"
            )
            return

    if not high_level_intentions:
        print(
            f"{bcolors.FAIL}No high-level intentions available.{bcolors.ENDC}"
        )
        return

    high_level_intentions = _deduplicate_high_level_intentions(
        high_level_intentions,
        verbose=agent.verbose,
    )

    final_intentions = [_build_intention(intent) for intent in high_level_intentions]

    # --- Update Agent State ---
    agent.intentions = deque(final_intentions)
    for desire_id in {intention.desire_id for intention in final_intentions}:
        update_desire_status(agent, desire_id, DesireStatus.ACTIVE)
    print(
        f"{bcolors.SYSTEM}Intention generation complete. Updated agent with {len(agent.intentions)} high-level intentions.{bcolors.ENDC}"
    )
    log_states(agent, ["intentions"])


__all__ = [
    "generate_intentions_from_desires",
]
