---
title: Structured Summaries And Failure Continuation
labels:
  - needs-triage
type: AFK
status: completed
---

## What to build

Emit parseable per-task result summaries for SBench orchestrator consumption and make task failure behavior explicit. Each selected task should report its task ID, outcome, cycles run, elapsed time, answer folder, and log path; errors should be recorded without crashing the remaining batch by default, with an option to stop on first failure for debugging runs.

## Acceptance criteria

- [x] Each completed task emits a parseable summary record containing task ID, outcome, cycles run, elapsed time, answer folder, and log path.
- [x] Outcome reporting preserves achieved, failed, terminal, stopped, interrupted, max-cycles, and error states from the existing final status checks.
- [x] A task error is reported in that task's summary while later selected tasks continue by default.
- [x] A stop-on-failure option stops the run after the first non-success or error outcome.
- [x] Runner exit behavior clearly distinguishes validation/configuration failure from completed runs that include task-level failures.
- [x] Summary formatting can be tested without invoking real model calls.

## Blocked by

- .prd/issues/008-no-argument-sbench-toy-runner-compatibility.md
- .prd/issues/009-cli-task-selection-and-validation.md
- .prd/issues/010-configured-scoped-bdi-task-execution.md
