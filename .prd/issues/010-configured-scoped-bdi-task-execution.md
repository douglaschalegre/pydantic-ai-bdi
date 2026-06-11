---
title: Configured Scoped BDI Task Execution
labels:
  - needs-triage
type: AFK
status: completed
---

## What to build

Propagate CLI runtime settings into each selected SBench BDI task run while preserving the existing task scope and BDI semantics. The runner should use the configured model, output directory, cycle limit, command timeout, cycle sleep, and verbosity; keep filesystem MCP and `run_in_task` scoped to the selected task folder; and leave deliverables in the task-local `answer/` directory.

## Acceptance criteria

- [x] `--model`, `--output-dir`, `--max-cycles`, `--command-timeout-seconds`, `--cycle-sleep-seconds`, and verbosity options populate the run configuration used by task execution.
- [x] Per-task log paths are deterministic, task-specific, and written under the configured output directory.
- [x] The filesystem MCP server is built with only the selected task folder path.
- [x] The `run_in_task` tool uses the selected task folder as its working directory and clamps command timeouts explicitly.
- [x] The runner leaves answer files in each task-local `answer/` folder and does not archive or move answers into SBench's permanent answer tree.
- [x] BDI Desire, Intention, Plan, and Plan Step logging behavior remains available for each task.

## Blocked by

- .prd/issues/008-no-argument-sbench-toy-runner-compatibility.md
- .prd/issues/009-cli-task-selection-and-validation.md
