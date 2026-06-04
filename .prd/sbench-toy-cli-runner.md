---
title: SBench Toy CLI Runner
labels:
  - needs-triage
status: draft
---

## Problem Statement

The BDI repository currently has a `toy.py` runner that can execute all SBench tasks. This is useful because the BDI harness already has a single-command workflow for the current benchmark. However, `toy.py` is configured through hardcoded constants for model name, SBench root, task root, output directory, maximum cycles, command timeout, cycle sleep, verbosity, and skipped tasks.

Those hardcoded constants make the BDI runner difficult to call from an external SBench orchestrator. The expanded SBench benchmark needs one central `run_benchmark.py` command that can execute BDI, Codex, and OpenCode across the same task matrix. For that to work cleanly, the BDI runner needs a stable command-line interface that allows SBench to select tasks, model, output path, timeout-related settings, and run behavior without editing source code.

The BDI runner should preserve its current behavior when run with no arguments, but it should also support explicit parameters for automated benchmark execution. It should continue to create task-local `answer/` outputs and task-specific BDI logs, while leaving final answer archiving to the SBench orchestrator.

## Solution

Refactor `toy.py` into a parameterized SBench BDI runner with a small command-line interface. The default invocation should behave like the current script, using the existing model, SBench root, tasks root, output directory, cycle limits, command timeout, cycle sleep, verbosity, and no skipped tasks unless defaults change intentionally later.

The new CLI should accept arguments that let an external orchestrator run a selected task or selected task list with predictable output. The key parameters should include SBench root, task selection, model name, output directory, max cycles, command timeout seconds, cycle sleep seconds, verbosity, and optional skip tasks. The runner should validate paths, discover tasks, run selected tasks sequentially, print a parseable summary, and preserve per-task logs.

The runner should not archive answers into SBench's permanent `answers/` tree. That responsibility belongs to the SBench orchestrator. The BDI runner should only execute the BDI agent against task folders and leave the produced files in each task's `answer/` directory. This keeps all harness answer archiving centralized and prevents BDI-specific output movement from diverging from Codex and OpenCode.

The refactor should separate configuration parsing, task discovery, agent creation, task execution, and summary reporting enough that the behavior can be tested without invoking real LLM calls.

## User Stories

1. As a benchmark runner, I want to run `toy.py` with no arguments, so that the existing BDI workflow continues to work.
2. As a benchmark runner, I want to pass `--sbench-root`, so that the runner can be called from an external SBench orchestrator.
3. As a benchmark runner, I want to pass `--tasks all`, so that the runner can execute every discovered SBench task.
4. As a benchmark runner, I want to pass a single task ID, so that the orchestrator can run BDI one task at a time.
5. As a benchmark runner, I want to pass multiple task IDs, so that I can run a selected subset without editing source code.
6. As a benchmark runner, I want task discovery to use folders containing `task.md`, so that new SBench tasks are picked up consistently.
7. As a benchmark runner, I want to pass `--model`, so that BDI can use the same model setting as Codex and OpenCode benchmark runs.
8. As a benchmark runner, I want to pass `--output-dir`, so that BDI logs can be written to the run-specific log location chosen by SBench.
9. As a benchmark runner, I want to pass `--max-cycles`, so that smoke and context-pressure tracks can use different BDI cycle limits.
10. As a benchmark runner, I want to pass `--command-timeout-seconds`, so that terminal tool limits are controlled by benchmark configuration.
11. As a benchmark runner, I want to pass `--cycle-sleep-seconds`, so that batch runs can tune sleep overhead without source edits.
12. As a benchmark runner, I want to control verbosity, so that interactive debugging and automated logs can use different output levels.
13. As a benchmark runner, I want to pass skip-task values, so that known-problem tasks can be excluded without editing the script.
14. As a benchmark runner, I want selected tasks to be validated before model execution starts, so that typos do not waste model budget.
15. As a benchmark runner, I want missing SBench roots to fail clearly, so that path configuration errors are easy to diagnose.
16. As a benchmark runner, I want missing task folders to fail clearly, so that orchestrator mistakes are easy to diagnose.
17. As a benchmark runner, I want a parseable per-task summary printed to stdout, so that the SBench orchestrator can record BDI results.
18. As a benchmark runner, I want the summary to include task ID, outcome, cycles run, elapsed time, answer folder, and log path, so that results can be archived and diagnosed.
19. As a benchmark runner, I want nonzero or error outcomes to be reported without crashing the whole selected task batch by default, so that one task does not prevent later BDI runs.
20. As a benchmark runner, I want an option to stop on first task failure, so that debugging runs can fail fast.
21. As a benchmark runner, I want BDI logs to remain per task, so that each task's Beliefs, Desires, Intentions, Plans, and Plan Steps can be inspected independently.
22. As a benchmark runner, I want log paths to be deterministic, so that the orchestrator can find and preserve them.
23. As a benchmark runner, I want the BDI runner to leave answer files in task-local `answer/` folders, so that the SBench orchestrator can archive every harness uniformly.
24. As a benchmark runner, I want the BDI runner not to move answers into SBench's permanent answer archive, so that archiving is not duplicated.
25. As a benchmark runner, I want the BDI runner to avoid reading hidden SBench evaluation files, so that BDI follows the same fixture exposure rules as other harnesses.
26. As a benchmark runner, I want the filesystem MCP server to remain scoped to the selected task folder, so that BDI sees only the intended task fixture.
27. As a benchmark runner, I want the `run_in_task` tool to continue using the task folder as its working directory, so that shell commands operate in the same scope as the task.
28. As a benchmark runner, I want command timeout clamping to remain explicit, so that tool calls cannot silently run forever.
29. As a benchmark runner, I want the model provider initialization to remain compatible with current Codex-provider BDI behavior, so that the refactor does not change model semantics.
30. As a benchmark runner, I want task ordering to be deterministic, so that repeated runs are easier to compare.
31. As a BDI researcher, I want the BDI runner to expose BDI trace logs consistently, so that SBench observability scoring can use them later.
32. As a BDI researcher, I want the BDI runner to preserve Desire, Intention, Plan, and Plan Step logging, so that interpretability evidence remains available.
33. As a BDI researcher, I want cycle counts recorded, so that BDI overhead can be studied separately from elapsed wall time.
34. As a BDI researcher, I want the runner to preserve existing task completion checks, so that achieved, failed, terminal, stopped, and interrupted outcomes remain visible.
35. As a BDI maintainer, I want configuration parsing separated from task execution, so that argument behavior can be tested without LLM calls.
36. As a BDI maintainer, I want task selection separated from agent execution, so that task filtering can be tested cheaply.
37. As a BDI maintainer, I want agent creation to receive an explicit run config, so that hardcoded globals are reduced.
38. As a BDI maintainer, I want summary reporting to be structured, so that future automation can parse it reliably.
39. As a BDI maintainer, I want the no-argument defaults documented in code or help text, so that existing users understand the behavior.
40. As a BDI maintainer, I want tests that avoid real model calls, so that CLI behavior can be validated in normal test runs.
41. As a SBench orchestrator developer, I want a stable BDI command contract, so that `run_benchmark.py` does not depend on editing `toy.py` constants.
42. As a SBench orchestrator developer, I want BDI to support one-task execution, so that the orchestrator can clean, run, archive, and repeat exactly like Codex and OpenCode.
43. As a SBench orchestrator developer, I want BDI to support run-specific output directories, so that logs for different runs do not overwrite each other.
44. As a SBench orchestrator developer, I want BDI command failures to have clear exit behavior, so that the orchestrator can distinguish timeout, error, and completed runs.
45. As a future maintainer, I want the runner to remain simple, so that it does not become a second benchmark orchestrator inside the BDI repository.

## Implementation Decisions

- Preserve the current no-argument behavior as the default workflow.
- Add a command-line interface to `toy.py` rather than creating a separate BDI runner initially.
- Accept SBench root, task selection, model, output directory, max cycles, command timeout seconds, cycle sleep seconds, verbosity, skip tasks, and stop-on-failure options.
- Treat `--tasks all` as the default full-suite mode.
- Allow task selection by task folder name.
- Validate selected tasks before starting model execution.
- Keep task ordering deterministic.
- Keep the filesystem MCP server scoped to the current task folder.
- Keep `run_in_task` scoped to the current task folder.
- Continue writing task-local deliverables under each task's `answer/` folder.
- Do not archive answer files into SBench's permanent answer tree from `toy.py`.
- Write BDI logs to the configured output directory with task-specific names.
- Emit per-task summaries that include task ID, outcome, cycles run, elapsed time, answer folder, and log path.
- Keep existing final status checks based on Desire status and final cycle status.
- Keep current BDI model/provider behavior unless the model name is explicitly overridden.
- Avoid changing BDI planning, execution, belief update, reconsideration, or logging semantics as part of this runner refactor.
- Refactor global constants into default configuration values used by argument parsing.
- Create a small run configuration object or equivalent structure to pass configuration through task discovery, agent creation, and execution.
- Keep the runner sequential in the first implementation.
- Do not add answer archive logic to the BDI repository; the SBench orchestrator owns archiving.
- Prefer parseable summary output, but do not require a full JSON event protocol in the first slice unless it stays small.

## Testing Decisions

Good tests should verify CLI and runner behavior without making real model calls. Tests should focus on parsing, task selection, validation, configuration propagation, summary formatting, and scoped path behavior.

- Test that no-argument parsing produces the current default configuration.
- Test that `--sbench-root` changes the discovered task root.
- Test that `--tasks all` selects all discovered task folders with `task.md`.
- Test that a single task selection returns only that task.
- Test that multiple task selections preserve deterministic ordering.
- Test that unknown task IDs fail validation before execution.
- Test that skip-task options remove selected tasks from the run set.
- Test that model, output directory, max cycles, command timeout, cycle sleep, and verbosity options populate the run configuration.
- Test that the filesystem server is built with the selected task path.
- Test that the `run_in_task` tool uses the selected task path as its working directory.
- Test that log paths are task-specific and use the configured output directory.
- Test that summary records include task ID, outcome, cycles run, elapsed time, answer folder, and log path.
- Test that a task error can be reported while later tasks continue by default.
- Test that stop-on-failure changes continuation behavior.
- Test that answer archiving is not performed by the BDI runner.

Prior art exists in the current `toy.py` SBench runner, the BDI lifecycle tests, and the SBench orchestrator PRD. The tests for this refactor should reuse the current runner behavior as the compatibility baseline.

## Out of Scope

- Changing BDI planning, execution, reconsideration, belief updates, or Desire/Intention/Plan semantics.
- Optimizing BDI runtime.
- Adding Codex or OpenCode execution to the BDI repository.
- Moving SBench answer archives from inside the BDI runner.
- Implementing SBench's multi-harness orchestrator in the BDI repository.
- Adding deterministic benchmark scoring.
- Adding parallel BDI task execution.
- Changing SBench task fixtures or expected answers.
- Publishing issues or results to GitHub.

## Further Notes

This PRD is the companion to the SBench benchmark orchestrator PRD. The SBench orchestrator should own multi-harness execution and answer archiving. The BDI repository should only make its existing SBench toy runner easier to call as one harness adapter.

The highest-priority compatibility rule is that running `toy.py` without arguments should continue to work as it does now. The highest-priority automation rule is that the SBench orchestrator must be able to invoke BDI for a specific task and then archive the produced `answer/` files using the same `rN` convention as Codex and OpenCode.
