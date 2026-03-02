"""Planning and deliberation for the BDI agent.

This module handles the two-stage LLM-based intention generation process that
converts high-level desires into detailed, actionable plans (intentions with steps).
"""

from collections import deque
import json
import re
from typing import TYPE_CHECKING, List

from helper.util import bcolors
from bdi.schemas import (
    Intention,
    HighLevelIntention,
    HighLevelIntentionList,
    DetailedStepList,
    PlanJudgementResult,
    DesireStatus,
    IntentionStep,
)
from bdi.logging import log_states
from bdi.prompts import (
    build_planning_stage1_prompt,
    build_planning_stage2_prompt,
    build_plan_coverage_judgement_prompt,
)

if TYPE_CHECKING:
    from bdi.agent import BDI


_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_text(value: str) -> str:
    """Normalize text for stable duplicate detection."""
    return _WHITESPACE_RE.sub(" ", value.strip().lower())


def _intention_fingerprint(hl_intention: HighLevelIntention) -> str:
    """Build a fingerprint for high-level intention deduplication."""
    return f"{hl_intention.desire_id}|{_normalize_text(hl_intention.description)}"


def _step_fingerprint(step: IntentionStep) -> str:
    """Build a fingerprint for cross-intention step deduplication."""
    if step.is_tool_call and step.tool_name:
        params = json.dumps(step.tool_params or {}, sort_keys=True)
        return (
            f"tool|{_normalize_text(step.tool_name)}|{_normalize_text(step.description)}|{params}"
        )
    return f"desc|{_normalize_text(step.description)}"


def _format_plan_context(intentions: List[Intention]) -> str:
    """Create a compact context block describing already planned work."""
    if not intentions:
        return "No intentions planned yet."

    lines: List[str] = []
    for idx, intention in enumerate(intentions, start=1):
        lines.append(
            f"{idx}. Desire '{intention.desire_id}' -> {intention.description or '(no description)'}"
        )
        for step_idx, step in enumerate(intention.steps, start=1):
            lines.append(f"   - Step {step_idx}: {step.description}")
    return "\n".join(lines)


def _filter_steps_by_indices(steps: List[IntentionStep], indices: List[int]) -> List[IntentionStep]:
    """Remove 1-based indexed steps from a step list."""
    to_remove = {i for i in indices if isinstance(i, int) and i >= 1}
    if not to_remove:
        return steps
    return [step for i, step in enumerate(steps, start=1) if i not in to_remove]


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


def _build_proposed_steps_text(steps: List[IntentionStep]) -> str:
    """Format generated steps for plan coverage judgement."""
    return "\n".join(
        [f"- [{index}] {step.description}" for index, step in enumerate(steps, start=1)]
    )


async def _apply_plan_coverage_judgement(
    agent: "BDI",
    high_level_intention: HighLevelIntention,
    steps: List[IntentionStep],
    *,
    beliefs_text: str,
    existing_plan_context: str,
) -> List[IntentionStep] | None:
    """Apply LLM plan coverage judgement and return remaining steps."""
    proposed_steps_text = _build_proposed_steps_text(steps)
    judgement_prompt = build_plan_coverage_judgement_prompt(
        high_level_intention.description,
        high_level_intention.desire_id,
        beliefs_text,
        existing_plan_context,
        proposed_steps_text,
    )

    try:
        judgement_result = await agent.run(
            judgement_prompt,
            output_type=PlanJudgementResult,
        )
    except Exception as judgement_error:
        if agent.verbose:
            print(
                f"{bcolors.WARNING}    Plan judgement unavailable, defaulting to keep: {judgement_error}{bcolors.ENDC}"
            )
        return steps

    if not judgement_result or not judgement_result.output:
        return steps

    judgement = judgement_result.output
    if judgement.decision == "skip":
        print(
            f"{bcolors.SYSTEM}    Skipping intention '{high_level_intention.description}' ({judgement.reason_category}): {judgement.reason}{bcolors.ENDC}"
        )
        return None

    if judgement.decision == "merge":
        before_merge_count = len(steps)
        steps = _filter_steps_by_indices(steps, judgement.redundant_step_indices)
        removed_count = before_merge_count - len(steps)
        if removed_count > 0 and agent.verbose:
            print(
                f"{bcolors.SYSTEM}    Coverage merge removed {removed_count} redundant step(s).{bcolors.ENDC}"
            )

    return steps


def _deduplicate_steps_against_existing_plan(
    steps: List[IntentionStep],
    planned_step_fingerprints: set[str],
) -> tuple[List[IntentionStep], int]:
    """Remove already-planned steps and return retained steps plus duplicate count."""
    unique_steps: List[IntentionStep] = []
    duplicate_count = 0

    for step in steps:
        fingerprint = _step_fingerprint(step)
        if fingerprint in planned_step_fingerprints:
            duplicate_count += 1
            continue

        planned_step_fingerprints.add(fingerprint)
        unique_steps.append(step)

    return unique_steps, duplicate_count


async def generate_intentions_from_desires(agent: "BDI") -> None:
    """Convert desires into detailed, actionable intentions using a two-stage LLM process.

    Stage 1: Generate high-level intentions (WHAT to achieve)
    Stage 2: For each high-level intention, generate detailed steps (HOW to achieve it)

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

    if agent.verbose:
        print(
            f"{bcolors.SYSTEM}Starting two-stage intention generation...{bcolors.ENDC}"
        )
    final_intentions: List[Intention] = []

    # --- Context Gathering (Common for both stages) ---
    desires_text = "\n".join(
        [f"- ID: {d.id}, Description: {d.description}" for d in agent.desires]
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

    # --- Stage 1: Generate High-Level Intentions ---
    # Check if explicit intentions were provided by the user
    # If so, use them directly instead of generating via LLM
    high_level_intentions: List[HighLevelIntention] = []

    if agent.initial_intention_guidance:
        # User provided explicit intentions - use them directly
        # Associate all intentions with the first active/pending desire
        # (In most cases, explicit intentions relate to a single primary desire)
        active_desires = [
            d
            for d in agent.desires
            if d.status in [DesireStatus.PENDING, DesireStatus.ACTIVE]
        ]
        primary_desire_id = (
            active_desires[0].id if active_desires else agent.desires[0].id
        )

        print(
            f"{bcolors.SYSTEM}Using {len(agent.initial_intention_guidance)} explicit intentions provided by user (skipping Stage 1 LLM).{bcolors.ENDC}"
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
        # No explicit intentions - generate via LLM (original Stage 1 behavior)
        if agent.verbose:
            print(
                f"{bcolors.SYSTEM}Stage 1: Generating high-level intentions...{bcolors.ENDC}"
            )
        prompt_stage1 = build_planning_stage1_prompt(desires_text, beliefs_text)
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
                    f"{bcolors.FAIL}Stage 1 failed: No high-level intentions generated.{bcolors.ENDC}"
                )
                return
            high_level_intentions = stage1_result.output.intentions
            print(
                f"{bcolors.SYSTEM}Stage 1 successful: Generated {len(high_level_intentions)} high-level intentions.{bcolors.ENDC}"
            )

        except Exception as e:
            print(
                f"{bcolors.FAIL}Stage 1 failed: Error during LLM call: {e}{bcolors.ENDC}"
            )
            return

    if not high_level_intentions:
        print(
            f"{bcolors.FAIL}No high-level intentions available for Stage 2.{bcolors.ENDC}"
        )
        return

    high_level_intentions = _deduplicate_high_level_intentions(
        high_level_intentions,
        verbose=agent.verbose,
    )

    # --- Stage 2: Generate Detailed Steps for Each High-Level Intention ---
    if agent.verbose:
        print(
            f"{bcolors.SYSTEM}Stage 2: Generating detailed steps for each intention...{bcolors.ENDC}"
        )

    planned_step_fingerprints: set[str] = set()

    for hl_intention in high_level_intentions:
        if agent.verbose:
            print(
                f"{bcolors.INTENTION}  Processing high-level intention for Desire '{hl_intention.desire_id}': {hl_intention.description}{bcolors.ENDC}"
            )

        existing_plan_context = _format_plan_context(final_intentions)

        prompt_stage2 = build_planning_stage2_prompt(
            hl_intention.description,
            hl_intention.desire_id,
            beliefs_text,
            existing_plan_context,
        )
        try:
            stage2_result = await agent.run(prompt_stage2, output_type=DetailedStepList)
            if (
                not stage2_result
                or not stage2_result.output
                or not stage2_result.output.steps
            ):
                print(
                    f"{bcolors.WARNING}  Stage 2 warning: No detailed steps generated for intention '{hl_intention.description}'. Skipping.{bcolors.ENDC}"
                )
                continue

            detailed_steps = stage2_result.output.steps
            if agent.verbose:
                print(
                    f"{bcolors.SYSTEM}    Generated {len(detailed_steps)} detailed steps.{bcolors.ENDC}"
                )

            judged_steps = await _apply_plan_coverage_judgement(
                agent,
                hl_intention,
                detailed_steps,
                beliefs_text=beliefs_text,
                existing_plan_context=existing_plan_context,
            )

            if judged_steps is None:
                continue
            detailed_steps = judged_steps

            if not detailed_steps:
                print(
                    f"{bcolors.WARNING}  Stage 2 warning: Intention '{hl_intention.description}' has no remaining steps after coverage judgement. Skipping.{bcolors.ENDC}"
                )
                continue

            unique_steps, duplicate_count = _deduplicate_steps_against_existing_plan(
                detailed_steps,
                planned_step_fingerprints,
            )

            if duplicate_count > 0:
                print(
                    f"{bcolors.SYSTEM}    Removed {duplicate_count} cross-intention duplicate step(s) for '{hl_intention.description}'.{bcolors.ENDC}"
                )

            if not unique_steps:
                print(
                    f"{bcolors.WARNING}  Stage 2 warning: All steps for intention '{hl_intention.description}' were already covered by previous plans. Skipping.{bcolors.ENDC}"
                )
                continue

            final_intention = Intention(
                desire_id=hl_intention.desire_id,
                description=hl_intention.description,
                steps=unique_steps,
            )
            final_intentions.append(final_intention)

        except Exception as e:
            print(
                f"{bcolors.FAIL}  Stage 2 failed for intention '{hl_intention.description}': Error during LLM call: {e}{bcolors.ENDC}"
            )

    # --- Update Agent State ---
    agent.intentions = deque(final_intentions)
    print(
        f"{bcolors.SYSTEM}Intention generation complete. Updated agent with {len(agent.intentions)} detailed intentions.{bcolors.ENDC}"
    )
    log_states(agent, ["intentions"])


__all__ = [
    "generate_intentions_from_desires",
]
