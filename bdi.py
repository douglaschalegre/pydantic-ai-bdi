from typing import (
    Dict,
    List,
    Any,
    Optional,
    TypeVar,
    Generic,
    Callable,
    Awaitable,
    Literal,
    Type,
    get_type_hints,
)
from collections import deque
from pydantic_ai import Agent
from pydantic_ai.tools import AgentDepsT
from pydantic_ai.agent import RunResultDataT
from util import bcolors
from schemas import (
    Belief,
    BeliefSet,
    Desire,
    DesireStatus,
    Intention,
    IntentionStep,
    HighLevelIntentionList,
    DetailedStepList,
    ReconsiderResult,
)
from datetime import datetime
import traceback

T = TypeVar("T")

__all__ = ["BDI", "Belief", "BeliefSet", "Desire", "Intention", "IntentionStep"]


class BDI(Agent, Generic[T]):
    """BDI (Belief-Desire-Intention) agent implementation.

    Extends the Pydantic AI Agent with a BDI architecture.
    Relies on the base Agent's capabilities for tool execution,
    including integration with MCP servers for external tools.
    """

    def __init__(
        self,
        *args,
        desires: List[str] = None,
        intentions: List[str] = None,
        verbose: bool = False,
        **kwargs,
    ):
        # Pass arguments to the base Pydantic AI Agent constructor
        # Ensure MCP configuration (e.g., server endpoints) is handled
        # either through these args/kwargs or environment variables
        # as supported by the underlying Pydantic AI Agent.
        super().__init__(*args, **kwargs)
        self.beliefs = BeliefSet()
        self.desires: List[Desire] = []
        self.intentions: deque[Intention] = deque()
        self.initial_intention_guidance: List[str] = intentions or []
        self.verbose = verbose

        self._initialize_string_desires(desires)

    def _initialize_string_desires(self, desire_strings: List[str]) -> None:
        """Initialize desires from string descriptions."""
        for i, desire_string in enumerate(desire_strings or []):
            desire_id = f"desire_{i + 1}"
            desire = Desire(
                id=desire_id,
                description=desire_string,
                priority=0.5,
            )
            self.desires.append(desire)
        self.log_states(["desires"])

    async def generate_intentions_from_desires(self) -> None:
        """Convert desires into detailed, actionable intentions using a two-stage LLM process."""
        if not self.desires:
            print(
                f"{bcolors.SYSTEM}No desires to generate intentions from.{bcolors.ENDC}"
            )
            return
        if self.intentions:
            print(
                f"{bcolors.SYSTEM}Intentions already exist, skipping generation.{bcolors.ENDC}"
            )
            return

        if self.verbose:
            print(
                f"{bcolors.SYSTEM}Starting two-stage intention generation...{bcolors.ENDC}"
            )
        final_intentions: List[Intention] = []

        # --- Context Gathering (Common for both stages) ---
        desires_text = "\n".join(
            [f"- ID: {d.id}, Description: {d.description}" for d in self.desires]
        )
        beliefs_text = (
            "\n".join(
                [
                    f"- {name}: {belief.value} (Source: {belief.source}, Certainty: {belief.certainty:.2f})"
                    for name, belief in self.beliefs.beliefs.items()
                ]
            )
            if self.beliefs.beliefs
            else "No current beliefs."
        )
        # Removed: tools_text based on self.tool_configs. The base Agent injects available tools.

        # --- Stage 1: Generate High-Level Intentions ---
        guidance_section = ""
        if self.initial_intention_guidance:
            guidance_text = "\n".join(
                [f"- {g}" for g in self.initial_intention_guidance]
            )
            guidance_section = f"\n\nUser-Provided Strategic Guidance (Consider these as high-level intentions to guide planning):\n{guidance_text}"

        if self.verbose:
            print(
                f"{bcolors.SYSTEM}Stage 1: Generating high-level intentions...{bcolors.ENDC}"
            )
        prompt_stage1 = f"""
        Given the following overall desires and current beliefs, identify high-level intentions required to fulfill these desires.
        For each relevant desire, propose one or more concise intentions. Each intention should represent a distinct goal or task achievable *by you, the AI agent*.

        Focus ONLY on WHAT needs to be done at a high level, but ensure these goals are achievable through information processing, analysis, or using the available tools.
        Do *not* propose intentions that require physical actions in the real world (e.g., installing hardware), direct interaction with physical systems beyond your tool capabilities, or capabilities you do not possess based on the available tools.

        Overall Desires:
        {desires_text}
        {guidance_section}

        Current Beliefs:
        {beliefs_text}

        Available Tools:
        (The underlying Pydantic AI agent will provide the available tools, including those from MCP, to the LLM.)

        Respond with a list of high-level intentions using the required format. Associate each intention with its corresponding desire ID.
        """
        try:
            # Use the base agent's run method
            stage1_result = await self.run(
                prompt_stage1, result_type=HighLevelIntentionList
            )
            if (
                not stage1_result
                or not stage1_result.data
                or not stage1_result.data.intentions
            ):
                print(
                    f"{bcolors.FAIL}Stage 1 failed: No high-level intentions generated.{bcolors.ENDC}"
                )
                # Log error details if available
                if stage1_result and hasattr(stage1_result, "error_details"):
                    print(
                        f"{bcolors.FAIL}Error details: {stage1_result.error_details}{bcolors.ENDC}"
                    )
                return
            high_level_intentions = stage1_result.data.intentions
            print(
                f"{bcolors.SYSTEM}Stage 1 successful: Generated {len(high_level_intentions)} high-level intentions.{bcolors.ENDC}"
            )

        except Exception as e:
            print(
                f"{bcolors.FAIL}Stage 1 failed: Error during LLM call: {e}{bcolors.ENDC}"
            )
            return

        # --- Stage 2: Generate Detailed Steps for Each High-Level Intention ---
        if self.verbose:
            print(
                f"{bcolors.SYSTEM}Stage 2: Generating detailed steps for each intention...{bcolors.ENDC}"
            )
        for hl_intention in high_level_intentions:
            if self.verbose:
                print(
                    f"{bcolors.INTENTION}  Processing high-level intention for Desire '{hl_intention.desire_id}': {hl_intention.description}{bcolors.ENDC}"
                )

            prompt_stage2 = f"""
            Your task is to create a detailed, step-by-step action plan to achieve the following high-level intention:
            '{hl_intention.description}' (This contributes to overall Desire ID: {hl_intention.desire_id})

            Consider the current beliefs and available tools to formulate the plan.
            Each step in the plan must be a single, concrete action that *you, the AI agent*, can perform. Steps MUST be one of the following:
            1. A specific call to an available tool (listed below), including necessary parameters based on context and beliefs.
            2. An internal information processing or analysis task (e.g., 'Analyze sensor data', 'Summarize report X', 'Compare belief A and B', 'Decide next action based on criteria Y').

            Do *not* generate steps requiring physical actions, interaction with the physical world outside of tool capabilities, or capabilities you do not possess.

            Current Beliefs:
            {beliefs_text}

            Available Tools:
            (The underlying Pydantic AI agent will provide the available tools, including those from MCP, to the LLM.)

            Generate a sequence of detailed steps required to execute this intention. Ensure the steps are logical and sequential.
            Structure the output as a list of steps according to the required format.
            Focus exclusively on HOW to achieve the intention '{hl_intention.description}' using only the allowed action types.
            Provide parameters for tool calls based on the context and beliefs.
            """
            try:
                # Use the base agent's run method
                stage2_result = await self.run(
                    prompt_stage2, result_type=DetailedStepList
                )
                if (
                    not stage2_result
                    or not stage2_result.data
                    or not stage2_result.data.steps
                ):
                    print(
                        f"{bcolors.WARNING}  Stage 2 warning: No detailed steps generated for intention '{hl_intention.description}'. Skipping.{bcolors.ENDC}"
                    )
                    # Log error details if available
                    if stage2_result and hasattr(stage2_result, "error_details"):
                        print(
                            f"{bcolors.WARNING}Error details: {stage2_result.error_details}{bcolors.ENDC}"
                        )
                    continue

                detailed_steps = stage2_result.data.steps
                if self.verbose:
                    print(
                        f"{bcolors.SYSTEM}    Generated {len(detailed_steps)} detailed steps.{bcolors.ENDC}"
                    )

                # Assemble the final intention
                final_intention = Intention(
                    desire_id=hl_intention.desire_id, steps=detailed_steps
                )
                final_intentions.append(final_intention)

            except Exception as e:
                print(
                    f"{bcolors.FAIL}  Stage 2 failed for intention '{hl_intention.description}': Error during LLM call: {e}{bcolors.ENDC}"
                )

        # --- Update Agent State ---
        self.intentions = deque(final_intentions)
        print(
            f"{bcolors.SYSTEM}Intention generation complete. Updated agent with {len(self.intentions)} detailed intentions.{bcolors.ENDC}"
        )
        self.log_states(["intentions"])

    async def _analyze_step_outcome_and_update_beliefs(
        self, step: IntentionStep, result: Optional[RunResultDataT]
    ) -> bool:
        """
        Analyzes the outcome of an executed step, updates beliefs, and determines success.

        Args:
            step: The IntentionStep that was executed.
            result: The result returned by the base Agent's run method.

        Returns:
            True if the step is considered successful, False otherwise.
        """
        if self.verbose:
            print(f"{bcolors.SYSTEM}  Analyzing step outcome...{bcolors.ENDC}")
        if not result:
            print(
                f"{bcolors.WARNING}  Analysis: Step failed - No result returned.{bcolors.ENDC}"
            )
            return False
        if hasattr(result, "error_details") and result.error_details:
            print(
                f"{bcolors.WARNING}  Analysis: Step failed - Execution error: {result.error_details}.{bcolors.ENDC}"
            )
            return False

        # --- Belief Update Placeholder ---
        if self.verbose:
            print(
                f"{bcolors.SYSTEM}  (Belief update check based on result: {result.data}){bcolors.ENDC}"
            )

        # --- Success Assessment (using LLM) ---
        assessment_prompt = f"""
        Original objective for the step: "{step.description}"
        Result obtained: "{result.data}"

        Based *only* on the result obtained, did the step successfully achieve its original objective?
        Respond with a boolean value: True for success, False for failure.
        """
        try:
            assessment_result = await self.run(assessment_prompt, result_type=bool)
            if assessment_result and assessment_result.data:
                if self.verbose:
                    print(
                        f"{bcolors.SYSTEM}  LLM Assessment: Step SUCCEEDED.{bcolors.ENDC}"
                    )
                return True
            else:
                failure_reason = (
                    assessment_result.data
                    if (assessment_result and assessment_result.data)
                    else "No assessment result or negative assessment"
                )
                print(
                    f"{bcolors.WARNING}  LLM Assessment: Step FAILED. Reason: {failure_reason}{bcolors.ENDC}"
                )
                return False
        except Exception as assess_e:
            print(
                f"{bcolors.FAIL}  Error during LLM success assessment: {assess_e}{bcolors.ENDC}"
            )
            return False

    async def _reconsider_current_intention(self) -> None:
        """
        Evaluates if the current intention's remaining plan is still valid
        based on the current beliefs. If not, removes the intention and
        marks the desire as PENDING for replanning.
        """
        if not self.intentions:
            if self.verbose:
                print(f"{bcolors.SYSTEM}No intentions to re-consider.{bcolors.ENDC}")
            return

        intention = self.intentions[0]

        # Should not happen if called correctly, but safeguard
        if intention.current_step >= len(intention.steps):
            return

        print(
            f"{bcolors.SYSTEM}  Reconsidering intention for desire '{intention.desire_id}'...{bcolors.ENDC}"
        )

        # Format current beliefs
        beliefs_text = (
            "\n".join(
                [
                    f"  - {name}: {b.value} (Certainty: {b.certainty:.2f})"
                    for name, b in self.beliefs.beliefs.items()
                ]
            )
            if self.beliefs.beliefs
            else "  No current beliefs."
        )

        # Format remaining steps
        remaining_steps_list = intention.steps[intention.current_step :]
        remaining_steps_text = "\n".join(
            [f"  - {s.description}" for s in remaining_steps_list]
        )

        reconsider_prompt = f"""
        Current Agent Beliefs:
        {beliefs_text}

        Remaining Plan Steps (for Desire ID '{intention.desire_id}'):
        {remaining_steps_text}

        Critically evaluate:
        1. Is this remaining plan still likely to succeed in achieving the original desire '{intention.desire_id}', considering the current beliefs?
        2. Are there any direct contradictions between the beliefs and the plan's assumptions or required actions (e.g., trying to use a device believed to be broken)?
        3. Is there a high probability of failure for upcoming steps based on the current beliefs?

        Respond with only with True if the plan seems sound to continue.
        Respond with False followed by a brief explanation if the plan is flawed, unlikely to succeed, or contradicted by beliefs.
        """

        try:
            if self.verbose:
                print(
                    f"{bcolors.SYSTEM}  Asking LLM to assess plan validity...{bcolors.ENDC}"
                )
            reconsider_result = await self.run(
                reconsider_prompt, result_type=ReconsiderResult
            )

            if (
                reconsider_result
                and reconsider_result.data
                and reconsider_result.data.valid
            ):
                if self.verbose:
                    print(
                        f"{bcolors.SYSTEM}  LLM Assessment: Plan remains VALID. Reason: {reconsider_result.data.reason}{bcolors.ENDC}"
                    )
            else:
                reason = (
                    reconsider_result.data.reason
                    if (
                        reconsider_result
                        and reconsider_result.data
                        and reconsider_result.data.reason
                    )
                    else "LLM assessment indicated invalidity or failed."
                )
                print(
                    f"{bcolors.WARNING}  LLM Assessment: Plan INVALID. Reason: {reason}{bcolors.ENDC}"
                )
                print(
                    f"{bcolors.INTENTION}  Removing invalid intention for desire '{intention.desire_id}'.{bcolors.ENDC}"
                )
                invalid_intention = self.intentions.popleft()

                # Mark the desire as PENDING to allow replanning
                for desire in self.desires:
                    if desire.id == invalid_intention.desire_id:
                        print(
                            f"{bcolors.DESIRE}  Setting desire '{desire.id}' back to PENDING.{bcolors.ENDC}"
                        )
                        desire.update_status(DesireStatus.PENDING, self.log_states)
                        break
                self.log_states(
                    ["intentions", "desires"]
                )  # Log state change immediately

        except Exception as recon_e:
            print(
                f"{bcolors.FAIL}  Error during intention reconsideration LLM call: {recon_e}{bcolors.ENDC}"
            )

    async def execute_intentions(self) -> None:
        """
        Executes one step of the current intention, analyzes the outcome,
        updates beliefs, and handles success or failure.
        Does NOT proceed to the next step if the current step fails analysis.
        """
        if not self.intentions:
            print(f"{bcolors.SYSTEM}No intentions to execute.{bcolors.ENDC}")
            return

        intention = self.intentions[0]

        # Check if intention is already complete
        if intention.current_step >= len(intention.steps):
            print(
                f"{bcolors.INTENTION}Intention for desire '{intention.desire_id}' already completed (found in execute_intentions).{bcolors.ENDC}"
            )
            # Ensure desire is marked achieved and intention is removed
            if intention in self.intentions:
                for desire in self.desires:
                    if desire.id == intention.desire_id:
                        if desire.status != DesireStatus.ACHIEVED:
                            desire.update_status(DesireStatus.ACHIEVED, self.log_states)
                        break
                self.intentions.popleft()
                self.log_states(["intentions", "desires"])
            return

        current_step = intention.steps[intention.current_step]
        print(
            f"{bcolors.INTENTION}Executing step {intention.current_step + 1}/{len(intention.steps)} for desire '{intention.desire_id}': {current_step.description}{bcolors.ENDC}"
        )

        step_result: Optional[RunResultDataT] = None
        step_succeeded: bool = False

        try:
            if current_step.is_tool_call and current_step.tool_name:
                if self.verbose:
                    print(
                        f"{bcolors.SYSTEM}  Attempting tool call via self.run: {current_step.tool_name}({current_step.tool_params}){bcolors.ENDC}"
                    )
                tool_prompt = f"Execute the tool '{current_step.tool_name}' with the following parameters: {current_step.tool_params or {}}. Perform this action now."
                step_result = await self.run(tool_prompt)
                print(
                    f"{bcolors.SYSTEM}  Tool '{current_step.tool_name}' result: {step_result.data}{bcolors.ENDC}"
                )
            else:
                if self.verbose:
                    print(
                        f"{bcolors.SYSTEM}  Executing descriptive step via self.run: {current_step.description}{bcolors.ENDC}"
                    )
                step_result = await self.run(current_step.description)
                if self.verbose:
                    print(
                        f"{bcolors.SYSTEM}  Step result: {step_result.data}{bcolors.ENDC}"
                    )

            step_succeeded = await self._analyze_step_outcome_and_update_beliefs(
                current_step, step_result
            )

            if step_succeeded:
                print(
                    f"{bcolors.INTENTION}  Step {intention.current_step + 1} successful.{bcolors.ENDC}"
                )
                # Increment step counter *only on success*
                intention.increment_current_step(
                    self.log_states
                )  # Log state change here

                # Check if this was the last step
                if intention.current_step >= len(intention.steps):
                    print(
                        f"{bcolors.INTENTION}Completed final step. Intention for desire '{intention.desire_id}' finished.{bcolors.ENDC}"
                    )
                    # Mark desire achieved and remove intention
                    for desire in self.desires:
                        if desire.id == intention.desire_id:
                            desire.update_status(DesireStatus.ACHIEVED, self.log_states)
                            break
                    # Remove completed intention (important: check it's still the first one)
                    if self.intentions and self.intentions[0] == intention:
                        self.intentions.popleft()
                    self.log_states(["intentions", "desires"])
            else:
                # Step failed analysis, but don't discard intention yet.
                # Reconsideration will handle if the whole plan is invalid.
                print(
                    f"{bcolors.WARNING}  Step {intention.current_step + 1} failed analysis. Intention progress paused. Reconsideration pending.{bcolors.ENDC}"
                )
                # Do not increment step counter. Beliefs were updated in _analyze...
                self.log_states(["beliefs"])  # Log updated beliefs after failure

        except Exception as e:
            print(
                f"{bcolors.FAIL}------------------------------------------------------------{bcolors.ENDC}"
            )
            print(
                f"{bcolors.FAIL}Exception during execution/analysis of step for intention '{intention.desire_id}':{bcolors.ENDC}"
            )
            traceback.print_exc()  # Print full traceback for debugging
            print(f"{bcolors.FAIL}Error Message: {e}{bcolors.ENDC}")
            print(
                f"{bcolors.FAIL}------------------------------------------------------------{bcolors.ENDC}"
            )

            # Mark intention/desire as FAILED due to unexpected error
            for desire in self.desires:
                if desire.id == intention.desire_id:
                    desire.update_status(DesireStatus.FAILED, self.log_states)
                    break
            # Remove failed intention
            if self.intentions and self.intentions[0] == intention:
                self.intentions.popleft()
            self.log_states(["intentions", "desires"])  # Log state change

    async def bdi_cycle(self) -> None:
        """Run one BDI reasoning cycle including reconsideration."""
        self.log_states(
            types=["beliefs", "desires", "intentions"],
            message="States before starting BDI cycle",
        )
        print(f"{bcolors.SYSTEM}\n--- BDI Cycle Start ---{bcolors.ENDC}")

        # 1. Belief Update (Triggered by Action Outcomes)
        # Beliefs are updated within _analyze_step_outcome_and_update_beliefs
        # after an action is taken in execute_intentions.
        # We still print current beliefs at the start.
        if self.verbose:
            print(f"{bcolors.BELIEF}Current Beliefs:{bcolors.ENDC}")
            self.log_states(["beliefs"])  # Use log_states for consistent formatting

        # 2. Deliberation / Desire Status Check
        # Check for active/pending desires.
        if self.verbose:
            print(f"{bcolors.DESIRE}Current Desires:{bcolors.ENDC}")
            self.log_states(["desires"])  # Use log_states for consistent formatting
        active_desires = [
            d
            for d in self.desires
            if d.status in [DesireStatus.PENDING, DesireStatus.ACTIVE]
        ]

        # 3. Intention Generation (if needed)
        # If we have active/pending desires but no intentions queued, generate them.
        if active_desires and not self.intentions:
            print(
                f"{bcolors.SYSTEM}No current intentions, but active/pending desires exist. Generating intentions...{bcolors.ENDC}"
            )
            await self.generate_intentions_from_desires()
        else:
            if self.verbose:
                print(f"{bcolors.INTENTION}Current Intentions:{bcolors.ENDC}")
                self.log_states(
                    ["intentions"]
                )  # Use log_states for consistent formatting
            if not self.intentions:
                print(
                    f"{bcolors.SYSTEM}No intentions pending and no active desires require new ones.{bcolors.ENDC}"
                )

        # 4. Intention Execution (One Step)
        if self.intentions:
            await self.execute_intentions()
        else:
            print(f"{bcolors.SYSTEM}No intentions to execute this cycle.{bcolors.ENDC}")

        # 5. Reconsideration (Plan Monitoring)
        # After executing a step (successfully or not), reconsider the current plan.
        if self.intentions:  # Check if an intention still exists
            current_intention = self.intentions[0]
            # Only reconsider if the intention wasn't just completed/removed by execute_intentions
            if current_intention.current_step < len(current_intention.steps):
                await self._reconsider_current_intention()
            else:
                # Intention was completed or removed during execution/analysis phase.
                print(
                    f"{bcolors.SYSTEM}  Skipping reconsideration: Current intention just completed or removed.{bcolors.ENDC}"
                )
                pass  # Keep this pass
        else:
            print(
                f"{bcolors.SYSTEM}  Skipping reconsideration: No intentions remaining.{bcolors.ENDC}"
            )

        print(f"{bcolors.SYSTEM}--- BDI Cycle End ---{bcolors.ENDC}")
        self.log_states(
            types=["beliefs", "desires", "intentions"],
            message="States after BDI cycle",
        )

    def log_states(
        self,
        types: list[Literal["beliefs", "desires", "intentions"]],
        message: str | None = None,
    ):
        if message:
            print(f"{bcolors.SYSTEM}{message}{bcolors.ENDC}")
        if "beliefs" in types:
            if self.verbose:
                belief_str = "\n".join(
                    [
                        f"  - {name}: {b.value} (Source: {b.source}, Certainty: {b.certainty:.2f}, Time: {datetime.fromtimestamp(b.timestamp).isoformat()})"
                        for name, b in self.beliefs.beliefs.items()
                    ]
                )
                print(
                    f"{bcolors.BELIEF}Beliefs:\n{belief_str or '  (None)'}{bcolors.ENDC}"
                )
            else:
                print(
                    f"{bcolors.BELIEF}Beliefs: {len(self.beliefs.beliefs)} items{bcolors.ENDC}"
                )
        if "desires" in types:
            if self.verbose:
                desire_str = "\n".join(
                    [
                        f"  - {d.id}: {d.description} (Status: {d.status.value}, Priority: {d.priority})"
                        for d in self.desires
                    ]
                )
                print(
                    f"{bcolors.DESIRE}Desires:\n{desire_str or '  (None)'}{bcolors.ENDC}"
                )
            else:
                print(
                    f"{bcolors.DESIRE}Desires: {len(self.desires)} items{bcolors.ENDC}"
                )
        if "intentions" in types:
            if self.verbose:
                intention_str = "\n".join(
                    [
                        f"  - Desire '{i.desire_id}': Next -> {i.steps[i.current_step].description if i.current_step < len(i.steps) else '(Completed)'} (Step {i.current_step + 1}/{len(i.steps)})"
                        for i in self.intentions
                    ]
                )
                print(
                    f"{bcolors.INTENTION}Intentions:\n{intention_str or '  (None)'}{bcolors.ENDC}"
                )
            else:
                print(
                    f"{bcolors.INTENTION}Intentions: {len(self.intentions)} items{bcolors.ENDC}"
                )
