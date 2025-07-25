from typing import (
    Dict,
    List,
    Any,
    Optional,
    TypeVar,
    Generic,
    Literal,
)
from collections import deque
from pydantic_ai import Agent
from pydantic_ai.agent import AgentRunResult
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
    PlanManipulationDirective,
)
from datetime import datetime
import traceback
import json

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
        enable_human_in_the_loop: bool = False,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.beliefs = BeliefSet()
        self.desires: List[Desire] = []
        self.intentions: deque[Intention] = deque()
        self.initial_intention_guidance: List[str] = intentions or []
        self.verbose = verbose
        self.enable_human_in_the_loop = enable_human_in_the_loop

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
            stage1_result = await self.run(
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
                stage2_result = await self.run(
                    prompt_stage2, output_type=DetailedStepList
                )
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
                if self.verbose:
                    print(
                        f"{bcolors.SYSTEM}    Generated {len(detailed_steps)} detailed steps.{bcolors.ENDC}"
                    )

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
        self, step: IntentionStep, result: Optional[AgentRunResult]
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

        if self.verbose:
            print(
                f"{bcolors.SYSTEM}  (Belief update check based on result: {result.output}){bcolors.ENDC}"
            )

        # Get history context
        intention = self.intentions[0]
        history_context = self._generate_history_context(intention)

        # --- Success Assessment (using LLM) ---
        assessment_prompt = f"""
        Original objective for the step: "{step.description}"
        Result obtained: "{result.output}"

        Recent step history:
        {history_context}

        Based on the result obtained and recent history, did the step successfully achieve its original objective?
        Consider the context of previous steps and their outcomes in your assessment.
        Respond with a boolean value: True for success, False for failure.
        """
        try:
            assessment_result = await self.run(assessment_prompt, output_type=bool)
            if assessment_result and assessment_result.output:
                if self.verbose:
                    print(
                        f"{bcolors.SYSTEM}  LLM Assessment: Step SUCCEEDED.{bcolors.ENDC}"
                    )
                return True
            else:
                failure_reason = (
                    assessment_result.output
                    if (assessment_result and assessment_result.output)
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

        if intention.current_step >= len(intention.steps):
            return

        print(
            f"{bcolors.SYSTEM}  Reconsidering intention for desire '{intention.desire_id}'...{bcolors.ENDC}"
        )

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

        remaining_steps_list = intention.steps[intention.current_step :]
        remaining_steps_text = "\n".join(
            [f"  - {s.description}" for s in remaining_steps_list]
        )

        # Get detailed history context for reconsideration
        history_context = self._generate_history_context(
            intention,
            max_history=5,  # Show more history for reconsideration
            include_details=True,  # Include detailed information
        )

        reconsider_prompt = f"""
        Current Agent Beliefs:
        {beliefs_text}

        Step History:
        {history_context}

        Remaining Plan Steps (for Desire ID '{intention.desire_id}'):
        {remaining_steps_text}

        Critically evaluate:
        1. Is this remaining plan still likely to succeed in achieving the original desire '{intention.desire_id}', considering the current beliefs and step history?
        2. Are there any patterns in the step history that suggest the plan needs adjustment?
        3. Are there any direct contradictions between the beliefs, history, and the plan's assumptions?
        4. Based on the history of successful and failed steps, should the remaining plan be modified?

        Respond with only with True if the plan seems sound to continue.
        Respond with False followed by a brief explanation if the plan is flawed, unlikely to succeed, or contradicted by beliefs.
        """

        try:
            if self.verbose:
                print(
                    f"{bcolors.SYSTEM}  Asking LLM to assess plan validity...{bcolors.ENDC}"
                )
            reconsider_result = await self.run(
                reconsider_prompt, output_type=ReconsiderResult
            )

            if (
                reconsider_result
                and reconsider_result.output
                and reconsider_result.output.valid
            ):
                if self.verbose:
                    print(
                        f"{bcolors.SYSTEM}  LLM Assessment: Plan remains VALID. Reason: {reconsider_result.output.reason}{bcolors.ENDC}"
                    )
            else:
                reason = (
                    reconsider_result.output.reason
                    if (
                        reconsider_result
                        and reconsider_result.output
                        and reconsider_result.output.reason
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

                for desire in self.desires:
                    if desire.id == invalid_intention.desire_id:
                        print(
                            f"{bcolors.DESIRE}  Setting desire '{desire.id}' back to PENDING.{bcolors.ENDC}"
                        )
                        desire.update_status(DesireStatus.PENDING, self.log_states)
                        break
                self.log_states(["intentions", "desires"])

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

        if intention.current_step >= len(intention.steps):
            print(
                f"{bcolors.INTENTION}Intention for desire '{intention.desire_id}' already completed (found in execute_intentions).{bcolors.ENDC}"
            )
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

        step_result: Optional[AgentRunResult] = None
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
                    f"{bcolors.SYSTEM}  Tool '{current_step.tool_name}' result: {step_result.output}{bcolors.ENDC}"
                )
            else:
                if self.verbose:
                    print(
                        f"{bcolors.SYSTEM}  Executing descriptive step via self.run: {current_step.description}{bcolors.ENDC}"
                    )
                step_result = await self.run(current_step.description)
                if self.verbose:
                    print(
                        f"{bcolors.SYSTEM}  Step result: {step_result.output}{bcolors.ENDC}"
                    )

            step_succeeded = await self._analyze_step_outcome_and_update_beliefs(
                current_step, step_result
            )

            beliefs_updated = {
                name: {"value": b.value, "source": b.source, "certainty": b.certainty}
                for name, b in self.beliefs.beliefs.items()
            }
            intention.add_to_history(
                step=current_step,
                result=step_result.output if step_result else "No result",
                success=step_succeeded,
                beliefs_updated=beliefs_updated,
            )

            if step_succeeded:
                print(
                    f"{bcolors.INTENTION}  Step {intention.current_step + 1} successful.{bcolors.ENDC}"
                )
                intention.increment_current_step(self.log_states)

                if intention.current_step >= len(intention.steps):
                    print(
                        f"{bcolors.INTENTION}Completed final step. Intention for desire '{intention.desire_id}' finished.{bcolors.ENDC}"
                    )
                    for desire in self.desires:
                        if desire.id == intention.desire_id:
                            desire.update_status(DesireStatus.ACHIEVED, self.log_states)
                            break
                    if self.intentions and self.intentions[0] == intention:
                        self.intentions.popleft()
                    self.log_states(["intentions", "desires"])
            else:
                print(
                    f"{bcolors.WARNING}  Step {intention.current_step + 1} failed analysis. Intention progress paused. Reconsideration pending.{bcolors.ENDC}"
                )

                hitl_success = False
                if self.enable_human_in_the_loop:
                    try:
                        hitl_success = await self._human_in_the_loop_intervention(
                            intention, current_step, step_result
                        )
                    except Exception as hitl_e:
                        print(
                            f"{bcolors.FAIL}Error during HITL intervention: {hitl_e}{bcolors.ENDC}"
                        )
                        if self.verbose:
                            traceback.print_exc()

                if hitl_success:
                    print(
                        f"{bcolors.SYSTEM}  HITL intervention successful. Step will be retried in next cycle.{bcolors.ENDC}"
                    )
                else:
                    self.log_states(["beliefs"])

        except Exception as e:
            print(
                f"{bcolors.FAIL}------------------------------------------------------------{bcolors.ENDC}"
            )
            print(
                f"{bcolors.FAIL}Exception during execution/analysis of step for intention '{intention.desire_id}':{bcolors.ENDC}"
            )
            traceback.print_exc()
            print(f"{bcolors.FAIL}Error Message: {e}{bcolors.ENDC}")
            print(
                f"{bcolors.FAIL}------------------------------------------------------------{bcolors.ENDC}"
            )

            beliefs_updated = {
                name: {"value": b.value, "source": b.source, "certainty": b.certainty}
                for name, b in self.beliefs.beliefs.items()
            }
            intention.add_to_history(
                step=current_step,
                result=f"Exception: {str(e)}",
                success=False,
                beliefs_updated=beliefs_updated,
            )

            for desire in self.desires:
                if desire.id == intention.desire_id:
                    desire.update_status(DesireStatus.FAILED, self.log_states)
                    break
            if self.intentions and self.intentions[0] == intention:
                self.intentions.popleft()
            self.log_states(["intentions", "desires"])

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
            self.log_states(["beliefs"])

        # 2. Deliberation / Desire Status Check
        # Check for active/pending desires.
        if self.verbose:
            print(f"{bcolors.DESIRE}Current Desires:{bcolors.ENDC}")
            self.log_states(["desires"])
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
                self.log_states(["intentions"])
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
            if not current_intention.steps or current_intention.current_step < len(
                current_intention.steps
            ):
                await self._reconsider_current_intention()
            else:
                print(
                    f"{bcolors.SYSTEM}  Skipping reconsideration: Current intention just completed, removed, or has no steps.{bcolors.ENDC}"
                )
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

    def _build_failure_context(
        self,
        intention: Intention,
        failed_step: IntentionStep,
        step_result: Optional[AgentRunResult],
    ) -> Dict[str, Any]:
        """Gathers all relevant information about a step failure into a structured dictionary."""
        context = {
            "desire_id": intention.desire_id,
            "failed_step_description": failed_step.description,
            "failed_step_number": intention.current_step + 1,
            "total_steps_in_plan": len(intention.steps),
            "is_tool_call": failed_step.is_tool_call,
            "tool_name": failed_step.tool_name if failed_step.is_tool_call else None,
            "tool_params": failed_step.tool_params
            if failed_step.is_tool_call
            else None,
            "step_result_output": step_result.output
            if step_result and hasattr(step_result, "output")
            else "No result data",
            "llm_step_assessment": "Step was deemed a FAILURE by internal analysis.",
            "current_beliefs": {
                name: {
                    "value": b.value,
                    "source": b.source,
                    "certainty": b.certainty,
                    "timestamp": datetime.fromtimestamp(b.timestamp).isoformat(),
                }
                for name, b in self.beliefs.beliefs.items()
            }
            if self.beliefs.beliefs
            else "No current beliefs.",
            "remaining_plan_steps": [
                {
                    "description": s.description,
                    "is_tool_call": s.is_tool_call,
                    "tool_name": s.tool_name,
                    "tool_params": s.tool_params,
                }
                for s in intention.steps[intention.current_step + 1 :]
            ],
            "original_failed_step_object": failed_step.model_dump(),
        }
        return context

    def _present_context_to_user(self, failure_context: Dict[str, Any]) -> None:
        """Presents the failure context to the user in a readable format."""
        print(
            f"{bcolors.FAIL}------------------------------------------------------------{bcolors.ENDC}"
        )
        print(
            f"{bcolors.FAIL}HUMAN INTERVENTION REQUIRED for Desire '{failure_context['desire_id']}'{bcolors.ENDC}"
        )
        print(
            f"{bcolors.FAIL}------------------------------------------------------------{bcolors.ENDC}"
        )
        print(
            f"Failed Step ({failure_context['failed_step_number']}/{failure_context['total_steps_in_plan']}): {failure_context['failed_step_description']}"
        )
        if failure_context["is_tool_call"]:
            print(
                f"  Tool Call: {failure_context['tool_name']}({json.dumps(failure_context['tool_params']) if failure_context['tool_params'] else '{}'})"
            )

        print(f"Step Result Data: {failure_context['step_result_output']}")

        print(f"Agent Assessment: {failure_context['llm_step_assessment']}")

        print("\nCurrent Beliefs:")
        if isinstance(failure_context["current_beliefs"], dict):
            if failure_context["current_beliefs"]:
                for name, b_details in failure_context["current_beliefs"].items():
                    print(
                        f"  - {name}: {b_details['value']} (Source: {b_details['source']}, Certainty: {b_details['certainty']:.2f}, Time: {b_details['timestamp']})"
                    )
            else:
                print("  (None)")
        else:
            print(f"  {failure_context['current_beliefs']}")

        if failure_context["remaining_plan_steps"]:
            print("\nRemaining Plan Steps:")
            for i, step_data in enumerate(failure_context["remaining_plan_steps"]):
                print(f"  {i + 1}. {step_data['description']}")
        else:
            print("\nNo remaining steps in this plan.")
        print(
            f"{bcolors.FAIL}------------------------------------------------------------{bcolors.ENDC}"
        )

    async def _interpret_user_nl_guidance(
        self, user_nl_instruction: str, failure_context: Dict[str, Any]
    ) -> Optional[PlanManipulationDirective]:
        """
        Interprets the user's natural language guidance using an LLM call
        and returns a structured PlanManipulationDirective.
        """
        if self.verbose:
            print(
                f"{bcolors.SYSTEM}  Interpreting user NL guidance via LLM...{bcolors.ENDC}"
            )

        """
        Prepare context for the LLM: Convert complex objects to JSON strings for easier inclusion in prompt
        The base Pydantic AI Agent handles tool configuration injection.
        We primarily need to provide the failure scenario and user input.

        Get available tool names and their descriptions/schemas for the LLM
        The base Agent class usually handles injecting tool schemas.
        If not directly available, we might need to re-format self.tool_configs if it exists
        or rely on the base Agent's prompt formatting.
        For now, assume the base self.run() handles tool schema presentation.
        """
        tools_description_for_llm = "Available tools will be provided by the system. Focus on their general capabilities if specific schemas aren't listed here."
        if hasattr(self, "tool_configs") and self.tool_configs:
            tools_list = []
            for tool_name, tool_config in self.tool_configs.items():
                schema_info = "Schema: (provided by system)"
                if hasattr(tool_config, "model_json_schema"):
                    schema_info = f"Input schema: {json.dumps(tool_config.model_json_schema().get('properties', {}))}"
                elif callable(tool_config):
                    docstring = getattr(tool_config, "__doc__", "No description.")
                    schema_info = (
                        f"Description: {docstring.strip() if docstring else 'N/A'}"
                    )
                tools_list.append(f"- {tool_name}: {schema_info}")
            if tools_list:
                tools_description_for_llm = (
                    "Available Tools (use these for new steps if applicable):\\n"
                    + "\\n".join(tools_list)
                )

        prompt = f"""
        The BDI agent encountered a failure during plan execution.
        The user has provided natural language guidance on how to proceed.
        Your task is to interpret this guidance and translate it into a structured PlanManipulationDirective.

        Current Failure Context:
        - Desire ID: {failure_context["desire_id"]}
        - Failed Step ({failure_context["failed_step_number"]}/{failure_context["total_steps_in_plan"]}): "{failure_context["failed_step_description"]}"
        - Original Failed Step Object: {json.dumps(failure_context["original_failed_step_object"])}
        - Is Tool Call: {failure_context["is_tool_call"]}
        - Tool Name: {failure_context["tool_name"] if failure_context["is_tool_call"] else "N/A"}
        - Tool Params Used: {json.dumps(failure_context["tool_params"]) if failure_context["is_tool_call"] and failure_context["tool_params"] else "N/A"}
        - Step Result Data: {json.dumps(failure_context["step_result_output"])}
        - Current Beliefs: {json.dumps(failure_context["current_beliefs"])}
        - Remaining Plan Steps (after failed one): {json.dumps(failure_context["remaining_plan_steps"])}

        User's Natural Language Guidance:
        "{user_nl_instruction}"

        {tools_description_for_llm}

        Instructions for you, the LLM:
        1. Analyze the user's guidance in the context of the failure.
        2. Determine the most appropriate 'manipulation_type' from the available literals in PlanManipulationDirective.
        3. If the user suggests modifying the current step, populate 'current_step_modifications' with a dictionary of changes. For tool calls, this is often a new 'tool_params' dictionary. For descriptive steps, it might be a new 'description'.
        4. If the user suggests new steps, populate 'new_steps_definition' with a list of dictionaries. Each dictionary must conform to the IntentionStep schema (fields: description, is_tool_call, tool_name, tool_params).
           If generating tool calls, ensure 'tool_name' is valid from the available tools and 'tool_params' are appropriate.
        5. If the user provides factual information to correct the agent's understanding, populate 'beliefs_to_update'. The key is the belief name, and the value is a dictionary for the Belief schema (e.g., {{"value": "new value", "source": "human_guidance", "certainty": 1.0}}).
        6. Provide a concise 'user_guidance_summary' explaining your interpretation and chosen action.
        7. If the user's guidance is unclear, a comment, or cannot be mapped to a specific plan manipulation, use 'COMMENT_NO_ACTION' and explain in the summary.
        """

        try:
            if self.verbose:
                print(
                    f"{bcolors.SYSTEM}  Sending user guidance to LLM for interpretation...{bcolors.ENDC}"
                )

            llm_response = await self.run(prompt, output_type=PlanManipulationDirective)

            if llm_response and llm_response.output:
                if self.verbose:
                    print(
                        f"{bcolors.SYSTEM}  LLM interpretation successful. Directive: {llm_response.output.model_dump_json(indent=2)}{bcolors.ENDC}"
                    )
                return llm_response.output
            else:
                error_msg = (
                    "LLM did not return valid data for PlanManipulationDirective."
                )
                print(f"{bcolors.FAIL}  {error_msg}{bcolors.ENDC}")
                return None
        except Exception as e:
            print(
                f"{bcolors.FAIL}  Exception during LLM call for NL guidance interpretation: {e}{bcolors.ENDC}"
            )
            traceback.print_exc()
            return None

    def _summarize_directive_for_user(
        self, directive: PlanManipulationDirective
    ) -> str:
        """Translates a PlanManipulationDirective into a human-readable summary."""
        summary_parts = [
            f"Action Type: {directive.manipulation_type.replace('_', ' ').title()}"
        ]
        summary_parts.append(f"LLM's Understanding: {directive.user_guidance_summary}")

        if (
            directive.manipulation_type == "MODIFY_CURRENT_AND_RETRY"
            and directive.current_step_modifications
        ):
            summary_parts.append(
                f"  - Modifications to current step: {json.dumps(directive.current_step_modifications)}"
            )

        if directive.new_steps_definition:
            if directive.manipulation_type in [
                "REPLACE_CURRENT_STEP_WITH_NEW",
                "INSERT_NEW_STEPS_BEFORE_CURRENT",
                "INSERT_NEW_STEPS_AFTER_CURRENT",
                "REPLACE_REMAINDER_OF_PLAN",
            ]:
                summary_parts.append("  - New Steps Proposed:")
                for i, step_def in enumerate(directive.new_steps_definition):
                    desc = step_def.get("description", "N/A")
                    tool_name = step_def.get("tool_name")
                    tool_params = step_def.get("tool_params")
                    step_summary = f"    {i + 1}. Description: '{desc}'"
                    if tool_name:
                        step_summary += f" (Tool: {tool_name}, Params: {json.dumps(tool_params) if tool_params else '{}'})"
                    summary_parts.append(step_summary)

        if (
            directive.manipulation_type == "UPDATE_BELIEFS_AND_RETRY"
            and directive.beliefs_to_update
        ):
            summary_parts.append("  - Belief Updates Proposed:")
            for name, belief_data in directive.beliefs_to_update.items():
                summary_parts.append(
                    f"    - '{name}': {belief_data.get('value', 'N/A')}"
                )

        return "\\n".join(summary_parts)

    async def _handle_user_abort_request(self, intention: Intention) -> None:
        """Helper to manage aborting an intention based on user request."""
        print(
            f"{bcolors.INTENTION}  User requested ABORT of intention for desire '{intention.desire_id}'.{bcolors.ENDC}"
        )
        original_desire_id = intention.desire_id

        if self.intentions and self.intentions[0] == intention:
            self.intentions.popleft()
            self.log_states(
                ["intentions"],
                message=f"Intention for desire '{original_desire_id}' removed due to user abort.",
            )
        else:
            try:
                self.intentions.remove(intention)
                self.log_states(
                    ["intentions"],
                    message=f"Intention for desire '{original_desire_id}' (not current) removed due to user abort.",
                )
            except ValueError:
                print(
                    f"{bcolors.WARNING}  Warning: Intention for desire '{original_desire_id}' not found in queue during abort.{bcolors.ENDC}"
                )

        for desire_obj in self.desires:
            if desire_obj.id == original_desire_id:
                desire_obj.update_status(DesireStatus.PENDING, self.log_states)
                print(
                    f"{bcolors.DESIRE}  Desire '{original_desire_id}' status set to PENDING for potential replanning.{bcolors.ENDC}"
                )
                break

    async def _apply_user_guided_action(
        self,
        directive: PlanManipulationDirective,
        intention: Intention,
    ) -> bool:
        """Applies the plan manipulation based on the LLM-interpreted and user-confirmed guidance."""

        idx = intention.current_step
        applied_successfully = False

        manip_type = directive.manipulation_type
        print(
            f"{bcolors.SYSTEM}  Applying user guidance: {manip_type} - {directive.user_guidance_summary}{bcolors.ENDC}"
        )

        try:
            if manip_type == "RETRY_CURRENT_AS_IS":
                applied_successfully = True

            elif manip_type == "MODIFY_CURRENT_AND_RETRY":
                if directive.current_step_modifications and idx < len(intention.steps):
                    step_to_modify = intention.steps[idx]
                    for (
                        field_name,
                        new_value,
                    ) in directive.current_step_modifications.items():
                        if hasattr(step_to_modify, field_name):
                            setattr(step_to_modify, field_name, new_value)
                        else:
                            print(
                                f"{bcolors.WARNING}  Cannot modify unknown field '{field_name}' in step.{bcolors.ENDC}"
                            )
                    self.log_states(
                        ["intentions"],
                        message=f"Intention step {idx} modified by user guidance.",
                    )
                    applied_successfully = True
                else:
                    print(
                        f"{bcolors.WARNING}  No modifications provided or invalid step index for MODIFY_CURRENT_AND_RETRY. Retrying as is.{bcolors.ENDC}"
                    )
                    applied_successfully = True

            elif manip_type in [
                "REPLACE_CURRENT_STEP_WITH_NEW",
                "INSERT_NEW_STEPS_BEFORE_CURRENT",
                "INSERT_NEW_STEPS_AFTER_CURRENT",
                "REPLACE_REMAINDER_OF_PLAN",
            ]:
                if directive.new_steps_definition:
                    new_steps_list = [
                        IntentionStep(**step_def)
                        for step_def in directive.new_steps_definition
                    ]

                    if manip_type == "REPLACE_CURRENT_STEP_WITH_NEW":
                        if idx < len(intention.steps):
                            intention.steps.pop(idx)
                            for i, new_step in enumerate(new_steps_list):
                                intention.steps.insert(idx + i, new_step)
                        else:
                            raise IndexError(
                                "Invalid step index for REPLACE_CURRENT_STEP_WITH_NEW"
                            )
                    elif manip_type == "INSERT_NEW_STEPS_BEFORE_CURRENT":
                        for i, new_step in enumerate(new_steps_list):
                            intention.steps.insert(idx + i, new_step)
                    elif manip_type == "INSERT_NEW_STEPS_AFTER_CURRENT":
                        insert_point = idx + 1
                        for i, new_step in enumerate(new_steps_list):
                            intention.steps.insert(insert_point + i, new_step)
                    elif manip_type == "REPLACE_REMAINDER_OF_PLAN":
                        intention.steps = intention.steps[:idx]
                        intention.steps.extend(new_steps_list)
                        if not intention.steps:
                            print(
                                f"{bcolors.WARNING}  Plan became empty after REPLACE_REMAINDER. Aborting intention.{bcolors.ENDC}"
                            )
                            await self._handle_user_abort_request(intention)
                            return True

                    self.log_states(
                        ["intentions"],
                        message=f"Intention modified by user guidance ({manip_type}).",
                    )
                    applied_successfully = True
                else:
                    print(
                        f"{bcolors.WARNING}  No new steps provided for {manip_type}. Reconsidering.{bcolors.ENDC}"
                    )
                    applied_successfully = False

            elif manip_type == "SKIP_CURRENT_STEP":
                if idx < len(intention.steps):
                    intention.increment_current_step(self.log_states)
                    if intention.current_step >= len(intention.steps):
                        print(
                            f"{bcolors.INTENTION}  Skipping step completed intention for desire '{intention.desire_id}'.{bcolors.ENDC}"
                        )
                        for desire_obj in self.desires:
                            if desire_obj.id == intention.desire_id:
                                desire_obj.update_status(
                                    DesireStatus.ACHIEVED, self.log_states
                                )
                                break
                        if self.intentions and self.intentions[0] == intention:
                            self.intentions.popleft()
                        self.log_states(["intentions", "desires"])
                    applied_successfully = True
                else:
                    print(
                        f"{bcolors.WARNING}  Cannot skip, already at end of plan or invalid index.{bcolors.ENDC}"
                    )
                    applied_successfully = False

            elif manip_type == "ABORT_INTENTION":
                await self._handle_user_abort_request(intention)
                applied_successfully = True

            elif manip_type == "UPDATE_BELIEFS_AND_RETRY":
                if directive.beliefs_to_update:
                    for name, belief_data_dict in directive.beliefs_to_update.items():
                        belief_data_dict.setdefault("name", name)
                        belief_data_dict.setdefault("source", "human_guidance")
                        belief_data_dict.setdefault("certainty", 1.0)
                        belief_data_dict.setdefault(
                            "timestamp", datetime.now().timestamp()
                        )
                        try:
                            self.beliefs.update(
                                name=name,
                                value=belief_data_dict["value"],
                                source=belief_data_dict["source"],
                                certainty=belief_data_dict["certainty"],
                            )
                        except KeyError as e:
                            print(
                                f"{bcolors.FAIL}  Failed to update belief '{name}' due to missing data: {e}{bcolors.ENDC}"
                            )
                        except Exception as e:
                            print(
                                f"{bcolors.FAIL}  Failed to update belief '{name}': {e}{bcolors.ENDC}"
                            )
                    self.log_states(
                        ["beliefs"], message="Beliefs updated by user guidance."
                    )
                else:
                    print(
                        f"{bcolors.WARNING}  User Guidance: Update beliefs, but no beliefs provided. Retrying as is.{bcolors.ENDC}"
                    )
                applied_successfully = True

            elif manip_type == "COMMENT_NO_ACTION":
                print(
                    f"{bcolors.SYSTEM}  User comment received, no direct action on plan. Reconsidering.{bcolors.ENDC}"
                )
                applied_successfully = False

            else:
                print(
                    f"{bcolors.WARNING}  Unknown or unhandled manipulation_type: {manip_type}. Reconsidering.{bcolors.ENDC}"
                )
                applied_successfully = False

        except IndexError as e:
            print(
                f"{bcolors.FAIL}  Error applying plan manipulation due to invalid step index: {e}{bcolors.ENDC}"
            )
            traceback.print_exc()
            applied_successfully = False
        except Exception as e:
            print(
                f"{bcolors.FAIL}  Error applying plan manipulation directive '{manip_type}': {e}{bcolors.ENDC}"
            )
            traceback.print_exc()
            applied_successfully = False

        return applied_successfully

    async def _human_in_the_loop_intervention(
        self,
        intention: Intention,
        failed_step: IntentionStep,
        step_result: Optional[AgentRunResult],
    ) -> bool:
        """
        Orchestrates the full human-in-the-loop interaction when a step fails.

        Returns:
            True if the user provided guidance that was successfully applied, False otherwise.
        """
        if self.verbose:
            print(
                f"{bcolors.SYSTEM}Starting human-in-the-loop intervention...{bcolors.ENDC}"
            )

        # 1. Build failure context
        failure_context = self._build_failure_context(
            intention, failed_step, step_result
        )

        # 2. Present context to user
        self._present_context_to_user(failure_context)

        # 3. Get user guidance
        print(
            f"\n{bcolors.SYSTEM}Please provide guidance on how to proceed (or 'quit' to exit HITL):{bcolors.ENDC}"
        )
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print(
                f"\n{bcolors.WARNING}HITL interaction interrupted. Continuing without user guidance.{bcolors.ENDC}"
            )
            return False

        if user_input.lower() in ["quit", "exit", "q"]:
            print(
                f"{bcolors.SYSTEM}User chose to exit HITL. Continuing without guidance.{bcolors.ENDC}"
            )
            return False

        if not user_input:
            print(
                f"{bcolors.WARNING}No guidance provided. Continuing without changes.{bcolors.ENDC}"
            )
            return False

        # 4. Interpret user guidance via LLM
        directive = await self._interpret_user_nl_guidance(user_input, failure_context)

        if not directive:
            print(
                f"{bcolors.FAIL}Failed to interpret user guidance. Continuing without changes.{bcolors.ENDC}"
            )
            return False

        # 5. Present interpretation back to user for confirmation
        summary = self._summarize_directive_for_user(directive)
        print(f"\n{bcolors.SYSTEM}LLM Interpretation of your guidance:{bcolors.ENDC}")
        print(summary)

        print(f"\n{bcolors.SYSTEM}Apply this guidance? (y/n/edit):{bcolors.ENDC}")
        try:
            confirmation = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(
                f"\n{bcolors.WARNING}Confirmation interrupted. Not applying guidance.{bcolors.ENDC}"
            )
            return False

        if confirmation in ["n", "no"]:
            print(
                f"{bcolors.SYSTEM}User declined to apply guidance. Trying again...{bcolors.ENDC}"
            )
            return await self._human_in_the_loop_intervention(
                intention, failed_step, step_result
            )
        elif confirmation in ["edit", "e"]:
            print(f"{bcolors.SYSTEM}Please provide revised guidance:{bcolors.ENDC}")
            try:
                revised_input = input("> ").strip()
                if revised_input:
                    revised_directive = await self._interpret_user_nl_guidance(
                        revised_input, failure_context
                    )
                    if revised_directive:
                        directive = revised_directive
                    else:
                        print(
                            f"{bcolors.FAIL}Failed to interpret revised guidance. Using original.{bcolors.ENDC}"
                        )
                else:
                    print(
                        f"{bcolors.WARNING}No revised guidance provided. Using original.{bcolors.ENDC}"
                    )
            except (EOFError, KeyboardInterrupt):
                print(
                    f"\n{bcolors.WARNING}Edit interrupted. Using original guidance.{bcolors.ENDC}"
                )
        elif confirmation not in ["y", "yes"]:
            print(f"{bcolors.WARNING}Invalid response. Assuming 'yes'.{bcolors.ENDC}")

        # 6. Apply the guidance
        applied_successfully = await self._apply_user_guided_action(
            directive, intention
        )

        if applied_successfully:
            print(f"{bcolors.SYSTEM}User guidance applied successfully.{bcolors.ENDC}")
            return True
        else:
            print(
                f"{bcolors.WARNING}Failed to apply user guidance completely.{bcolors.ENDC}"
            )
            return False

    def _generate_history_context(
        self, intention: Intention, max_history: int = 3, include_details: bool = False
    ) -> str:
        """
        Generates a formatted context string from the intention's step history.

        Args:
            intention: The Intention object containing the step history
            max_history: Maximum number of recent steps to include (default: 3)
            include_details: Whether to include detailed information about each step (default: False)

        Returns:
            A formatted string containing the step history context
        """
        if not intention.step_history:
            return "No previous steps executed."

        recent_history = intention.step_history[-max_history:]

        history_lines = []
        for h in recent_history:
            step_info = f"Step {h.step_number}: {h.step_description} - {'Success' if h.success else 'Failed'}"

            if include_details:
                details = [
                    f"  Result: {h.result}",
                    f"  Timestamp: {datetime.fromtimestamp(h.timestamp).isoformat()}",
                    "  Beliefs Updated:",
                ]

                for belief_name, belief_data in h.beliefs_updated.items():
                    details.append(
                        f"    - {belief_name}: {belief_data['value']} (Certainty: {belief_data['certainty']:.2f})"
                    )

                step_info += "\n" + "\n".join(details)

            history_lines.append(step_info)

        return "\n".join(history_lines)
