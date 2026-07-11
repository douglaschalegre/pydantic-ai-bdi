"""Planning and deliberation for the BDI agent.

This module converts active desires into high-level intentions. Each generated
intention is executed as one descriptive step, letting the execution agent use
tools and reconcile outcomes without pre-expanding a brittle detailed plan.
"""

from collections import deque
import re
from typing import TYPE_CHECKING, List

from voluntas._utils import bcolors
from voluntas.schemas import (
    Intention,
    HighLevelIntention,
    HighLevelIntentionList,
    DesireStatus,
    Plan,
    PlanStep,
)
from voluntas.logging import log_states
from voluntas.prompts import build_planning_stage1_prompt
from voluntas.state_transitions import update_desire_status

if TYPE_CHECKING:
    from voluntas.agent import BDI


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
        active_plan=Plan(
            steps=[PlanStep(description=high_level_intention.description)],
        ),
    )


def _select_high_level_intention(
    high_level_intentions: List[HighLevelIntention],
    pending_desire_ids: set[str],
) -> HighLevelIntention | None:
    """Return the first planner output targeting a pending Desire."""
    for high_level_intention in high_level_intentions:
        if high_level_intention.desire_id in pending_desire_ids:
            return high_level_intention
    return None


async def generate_intentions_from_desires(agent: "BDI") -> None:
    """Convert desires into high-level executable intentions.

    The planner performs one planning pass and commits one pending Desire as one
    Intention with one Plan.

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

    pending_desires = [d for d in agent.desires if d.status is DesireStatus.PENDING]
    if not pending_desires:
        print(f"{bcolors.SYSTEM}No pending desires to plan for.{bcolors.ENDC}")
        return

    if agent.verbose:
        print(
            f"{bcolors.SYSTEM}Starting single-stage intention generation...{bcolors.ENDC}"
        )

    # --- Context Gathering ---
    desires_text = "\n".join(
        [f"- ID: {d.id}, Description: {d.description}" for d in pending_desires]
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
        # User provided explicit intentions - use the first one for the next
        # pending Desire so planning still commits only one Intention.
        primary_desire_id = (
            pending_desires[0].id if pending_desires else agent.desires[0].id
        )

        print(
            f"{bcolors.SYSTEM}Using first explicit intention provided by user (skipping planning LLM).{bcolors.ENDC}"
        )

        intention_desc = agent.initial_intention_guidance[0]
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

    selected_intention = _select_high_level_intention(
        high_level_intentions,
        {desire.id for desire in pending_desires},
    )
    if selected_intention is None:
        print(
            f"{bcolors.FAIL}No generated intention targeted a pending desire.{bcolors.ENDC}"
        )
        return

    final_intention = _build_intention(selected_intention)

    # --- Update Agent State ---
    agent.intentions = deque([final_intention])
    update_desire_status(agent, final_intention.desire_id, DesireStatus.ACTIVE)
    print(
        f"{bcolors.SYSTEM}Intention generation complete. Updated agent with one high-level intention.{bcolors.ENDC}"
    )
    log_states(agent, ["intentions"])


__all__ = [
    "generate_intentions_from_desires",
]
