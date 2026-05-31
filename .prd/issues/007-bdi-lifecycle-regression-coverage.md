---
title: BDI Lifecycle Regression Coverage
labels:
  - needs-triage
type: AFK
status: completed
---

## What to build

Add regression coverage and observable lifecycle checks for the refactored BDI flow. The tests and logs should make it clear that the agent uses one active Intention, progresses through Plan Steps, avoids success-path reconsideration loops, applies cheaper belief updates, and remains benchmark-oriented without abandoning BDI semantics.

## Acceptance criteria

- [x] Regression tests cover one active Intention with multiple Plan Steps from adoption through completion.
- [x] Regression tests cover no reconsideration loop after successful Plan Step progress.
- [x] Regression tests cover batch belief update behavior in an execution-like path.
- [x] Logs expose enough Desire, Intention, Plan, and Plan Step state to diagnose lifecycle regressions.
- [x] Benchmark-relevant regression coverage demonstrates progress toward write and verification phases without repeated pending-state replanning.

## Blocked by

- .prd/issues/001-batch-belief-updates.md
- .prd/issues/003-single-active-intention-deliberation.md
- .prd/issues/004-conservative-plan-reconsideration.md
- .prd/issues/005-plan-repair-preserves-commitment.md
