---
title: No-Argument SBench Toy Runner Compatibility
labels:
  - needs-triage
type: AFK
status: completed
---

## What to build

Refactor `toy.py` behind an explicit run configuration while preserving the current no-argument SBench BDI workflow. Running the script without CLI arguments should still discover the default SBench task root, use the current model and runtime defaults, execute tasks sequentially, and keep existing BDI execution semantics.

## Acceptance criteria

- [x] No-argument parsing produces the current default model, SBench root, tasks root, output directory, max cycles, command timeout, cycle sleep, verbosity, and skip-task values.
- [x] `python toy.py` still creates the default output directory, discovers default SBench tasks, initializes the current Codex provider/model behavior, and runs selected tasks sequentially.
- [x] Configuration parsing is separated from task execution enough to unit test default values without invoking real model calls.
- [x] Agent creation receives explicit configuration rather than reading runtime options from hardcoded globals.
- [x] Help text or code-level defaults document the no-argument behavior for existing runner users.

## Blocked by

None - can start immediately
