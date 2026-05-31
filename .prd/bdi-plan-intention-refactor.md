---
title: BDI Intention, Plan, Reconsideration, and Belief Update Refactor
labels:
  - needs-triage
status: draft
---

## Problem Statement

The agent is intended to be a Belief-Desire-Intention implementation that can also perform benchmark-style tasks with practical cost and speed. Current behavior does not fully match the intended BDI semantics. The agent treats many pieces of work as separate Intentions for the same Desire, rather than treating the Intention as the committed goal and the Plan as the actionable strategy for achieving it.

This mismatch causes the monitoring and reconsideration flow to evaluate small units of work as though each one should satisfy the whole Desire. Useful progress is repeatedly invalidated, the Desire is returned to pending, similar plans are regenerated, and benchmark runs time out before reaching write and verification phases.

The agent also spends too much time and cost on belief updates. Each step can extract many beliefs, resolve belief names, evaluate updates, and sometimes repeat extraction for failed attempts. This creates large overhead compared with other agent harnesses, especially when tasks require many local-file facts and intermediate decisions.

## Solution

Refactor the architecture so BDI concepts are represented explicitly and consistently.

Desires are candidate goals. An Intention is the single committed Desire the agent is actively pursuing. A Plan is the current executable strategy for realizing that Intention. A Plan contains ordered Plan Steps and Plan Step History.

The agent will deliberate only when it has no active Intention. Deliberation selects one Desire and adopts one Intention with one Plan. The agent will keep pursuing that Intention until the Desire succeeds, fails, or the Plan is repaired/replaced enough times to prove the committed Desire is not achievable. The agent will not initially interrupt an active Intention for a newly higher-priority Desire.

Reconsideration will become Plan-aware and conservative. Successful Plan Step progress should normally continue without reconsideration. Reconsideration should run after failures, contradictions, or stale assumptions, and it should repair or replace the Plan rather than de-adopting the Intention unless the committed Desire is impossible.

Belief updates will be batched, deduplicated, and deterministic where possible. Exact normalized belief names should upsert without LLM calls. Ambiguous belief names or conflicting values should be resolved in a single batch operation. Failed-step retry context should reuse already extracted beliefs instead of extracting them again.

## User Stories

1. As a BDI agent developer, I want Desires to represent candidate goals, so that the architecture matches standard BDI terminology.
2. As a BDI agent developer, I want an Intention to represent one committed Desire, so that commitment is explicit and stable.
3. As a BDI agent developer, I want a Plan to represent the executable strategy for an Intention, so that action sequencing is not confused with commitment.
4. As a BDI agent developer, I want Plan Steps to live inside Plans, so that step execution does not dilute the meaning of Intention.
5. As a BDI agent developer, I want Plan Step History to live inside Plans, so that plan progress and plan failures have strong locality.
6. As a benchmark runner, I want the agent to avoid repeatedly replanning after useful progress, so that tasks complete within the time budget.
7. As a benchmark runner, I want the agent to continue after successful Plan Steps without unnecessary reconsideration, so that LLM calls are reserved for meaningful decisions.
8. As a benchmark runner, I want the agent to repair the current Plan after failures, so that temporary execution problems do not reset the whole Desire lifecycle.
9. As a benchmark runner, I want the agent to select one Desire at a time, so that new beliefs from the current task inform later plan generation.
10. As a benchmark runner, I want pending Desires to wait while an active Intention is being pursued, so that the agent maintains strong commitment.
11. As a benchmark runner, I want the agent to avoid speculative plans for other Desires, so that it does not waste budget on stale future work.
12. As a benchmark runner, I want completed Plan Steps to be remembered as completed coverage, so that replanning does not rediscover the same facts repeatedly.
13. As a benchmark runner, I want plan repair to preserve useful beliefs and completed work, so that the agent moves forward rather than looping.
14. As a benchmark runner, I want the agent to reach write and verification phases more reliably, so that benchmark tasks are actually completed.
15. As a BDI researcher, I want the current Intention to persist through ordinary Plan repair, so that the Implementation reflects commitment rather than opportunistic task switching.
16. As a BDI researcher, I want Desire failure to mean the committed goal is impossible or exhausted, so that failed Plans are not incorrectly treated as failed Desires.
17. As a BDI researcher, I want the agent to deliberate only when no Intention is active, so that deliberation and execution remain separate phases.
18. As a BDI researcher, I want future interruption policy to be explicit, so that commitment semantics are not weakened accidentally.
19. As an agent maintainer, I want planning to produce one Intention with one Plan, so that planning output is easier to reason about and test.
20. As an agent maintainer, I want reconsideration to evaluate the whole active Plan, so that it does not invalidate useful remaining work based on an isolated step.
21. As an agent maintainer, I want reconsideration to return structured outcomes, so that plan repair, plan replacement, and Desire failure are distinct decisions.
22. As an agent maintainer, I want belief extraction to happen once per step outcome, so that retry handling does not duplicate work.
23. As an agent maintainer, I want duplicate beliefs to be removed before update evaluation, so that belief processing remains cheap and predictable.
24. As an agent maintainer, I want exact normalized belief names to upsert deterministically, so that common belief updates do not require LLM calls.
25. As an agent maintainer, I want ambiguous belief resolutions to be batched, so that belief semantics remain flexible without excessive cost.
26. As an agent maintainer, I want stale or volatile beliefs to be handled carefully, so that old file-system facts do not mislead later planning.
27. As an agent maintainer, I want logs to show Desire, Intention, Plan, and Plan Step state separately, so that debugging reveals the correct lifecycle layer.
28. As an agent maintainer, I want tests around external behavior of planning, execution, reconsideration, and belief updates, so that future refactors preserve BDI semantics.
29. As a contributor, I want the Plan module to have a small Interface with high Depth, so that plan advancement, repair, replacement, and history recording are localized.
30. As a contributor, I want the belief update module to have a small batch Interface, so that callers do not need to understand name resolution, deduplication, and update rules.
31. As a contributor, I want the reconsideration module to have a clear Plan-level Interface, so that it cannot accidentally clear unrelated Desire progress.
32. As a contributor, I want the planning module to select only the next committed Intention, so that planning has high Leverage without overproducing speculative work.
33. As a user of the BDI harness, I want task performance to be closer to other agent harnesses, so that choosing BDI does not impose unacceptable time and cost overhead.
34. As a user of the BDI harness, I want the implementation to remain recognizably BDI, so that benchmark performance is not achieved by abandoning the architecture.
35. As a user of the BDI harness, I want tool and file access concerns noted but deferred, so that the highest-impact semantic and cost problems are addressed first.

## Implementation Decisions

- Introduce a dedicated Plan Module that owns Plan state, Plan Steps, Plan Step History, Plan status, step advancement, and completion checks.
- Keep Intention as the committed Desire wrapper rather than the container for raw executable steps.
- Change the Intention Interface so it owns one active Plan directly.
- Keep exactly one active Intention at a time for the initial refactor.
- Do not add an interruption policy initially; pending Desires wait until the active Intention succeeds, fails, or exhausts repair.
- Replace list-based planning output with a single next-intention decision.
- The planning Module should deliberate over available Desires and current Beliefs, select one Desire, and produce one committed Intention with one Plan.
- Planning should not produce speculative Plans for other pending Desires because later Beliefs may change the correct Plan.
- Reconsideration becomes a Plan Reconsideration Module, not an Intention queue validator.
- Plan reconsideration should evaluate the active Plan as a whole, including completed Plan Steps, remaining Plan Steps, current Beliefs, and relevant failure history.
- Successful Plan Step progress should not trigger normal reconsideration.
- Failed Plan Steps should trigger Plan repair or Plan replacement before Desire failure is considered.
- Desire failure should be reserved for impossible, exhausted, or explicitly failed committed goals.
- The state transition Module should distinguish Desire lifecycle transitions from Plan lifecycle transitions.
- The execution Module should execute the current Plan Step from the active Intention's Plan.
- The execution Module should record results into Plan Step History.
- The desire satisfaction check should run when a Plan completes, not when a one-step pseudo-Intention completes.
- Replanning should preserve useful completed coverage and Beliefs rather than clearing all work for the Desire.
- Logging should display the active Desire, active Intention, active Plan, next Plan Step, Plan Step index, and Plan status separately.
- Human-in-the-loop plan manipulation should target the Plan Interface rather than mutating Intention step fields directly.
- Belief update handling should expose a batch Interface that accepts extracted beliefs from a step outcome.
- The batch belief update Interface should deduplicate incoming beliefs before update evaluation.
- The batch belief update Interface should use deterministic exact-name upsert for normalized belief names.
- The batch belief update Interface should invoke LLM resolution only when names or values are genuinely ambiguous.
- Failed-step retry context should reuse extracted beliefs from the first analysis path instead of running another belief extraction pass.
- Tool/file access through a dedicated Adapter remains a known low-priority improvement, but it is out of the main implementation path for this PRD.

## Testing Decisions

- Good tests should assert external BDI behavior rather than implementation details.
- Planning tests should verify that, given multiple pending Desires and Beliefs, the planner selects exactly one Desire and returns one committed Intention with one Plan.
- Planning tests should verify that future Desires are not pre-planned while an active Intention exists.
- Cycle tests should verify that an active Intention prevents deliberation over other pending Desires.
- Execution tests should verify that successful Plan Steps advance the Plan and record Plan Step History.
- Execution tests should verify that Plan completion triggers Desire satisfaction assessment.
- Reconsideration tests should verify that successful progress does not automatically invoke Plan reconsideration.
- Reconsideration tests should verify that failed Plan Steps trigger Plan repair or replacement without immediately de-adopting the Intention.
- State transition tests should verify that Plan failure and Desire failure are separate outcomes.
- State transition tests should verify that a committed Intention persists across Plan repair.
- Belief update tests should verify deterministic exact-name upsert without LLM resolution.
- Belief update tests should verify deduplication of repeated extracted beliefs.
- Belief update tests should verify that ambiguous beliefs are resolved through one batch operation.
- Retry tests should verify that failed-step belief extraction is not duplicated for retry history.
- Logging tests should verify that the observable state output distinguishes Desire, Intention, Plan, and Plan Step concepts.
- Prior art exists in the current BDI planning, execution, state transition, and schema tests; those tests should be migrated to the new Desire, Intention, and Plan lifecycle semantics.

## Out of Scope

- Interrupting an active Intention for a newly higher-priority Desire is out of scope for the initial refactor.
- Running multiple active Intentions concurrently is out of scope.
- Speculative Plan generation for pending Desires is out of scope.
- Direct tool/file Adapter refactoring is out of scope, though it remains a noted low-priority architecture improvement.
- Publishing this PRD to GitHub or any external issue tracker is out of scope.
- Changing benchmark task definitions is out of scope.
- Replacing the BDI architecture with a generic agent harness is out of scope.

## Further Notes

The benchmark logs showed one successful task and two timed-out tasks. The successful task completed through broad descriptive execution. The timed-out tasks showed repeated replanning, invalidated remaining plans, path-related tool confusion, and expensive belief processing.

The highest-leverage fix is to restore the BDI semantic seam between Desire, Intention, and Plan. The second highest-leverage fix is to make belief updates cheaper and less repetitive. These changes should improve task completion speed while preserving the BDI identity of the agent.

The desired architecture favors strong commitment. Once a Desire is adopted as an Intention, the agent should continue pursuing it until success, failure, or Plan repair exhaustion. This keeps the Implementation faithful to BDI while still allowing practical task completion.
