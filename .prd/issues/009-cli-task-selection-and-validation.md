---
title: CLI Task Selection And Validation
labels:
  - needs-triage
type: AFK
status: completed
---

## What to build

Add CLI-controlled SBench task selection to `toy.py` so an external orchestrator can choose all tasks, one task, or a selected task subset without editing source. The runner should discover task folders by `task.md`, apply skip-task filters, validate all requested tasks before model execution starts, and keep task ordering deterministic.

## Acceptance criteria

- [x] `--sbench-root` changes the SBench root and derived tasks root used for discovery.
- [x] `--tasks all` selects every discovered folder containing `task.md` in deterministic order.
- [x] `--tasks <task-id>` and multiple task IDs select only valid task folders while preserving deterministic run order.
- [x] Unknown task IDs, missing SBench roots, missing task roots, and empty discovered task sets fail clearly before any model execution starts.
- [x] Skip-task options remove selected tasks from the run set without requiring source edits.

## Blocked by

- .prd/issues/008-no-argument-sbench-toy-runner-compatibility.md
