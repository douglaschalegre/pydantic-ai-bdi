# TAC BDI Agent Runner

This folder contains a BDI-based runner for TheAgentCompany tasks.

The runner creates a `BDI` agent with tools to:
- Read `/instruction/task.md` from the task container
- Run arbitrary shell commands in the container
- Inspect `/workspace`, `/instruction`, and `/utils`

## Prerequisites

1. TAC infra containers are running.
2. Python dependencies are installed in repo root:

```bash
cd /Users/douglas/code/masters/pydantic-ai-bdi
uv sync
```

## Modes

### Manual container mode

Use this when you already started and initialized the TAC container yourself:

```bash
uv run python theagentcompany/run_tac_bdi.py \
  --container tac-test \
  --verbose
```

### Managed single-task mode

Use this when the runner should create the task container, run `/utils/init.sh`, wait for `All services are ready!`, then start the BDI agent:

```bash
uv run python theagentcompany/run_tac_bdi.py \
  --task-image ghcr.io/theagentcompany/admin-arrange-meeting-rooms-image:1.0.0 \
  --structured-log-dir theagentcompany/tac-structured-logs \
  --verbose
```

### Managed batch mode with resume state

This mode reads task images from `tac-tasks.md`, uses the task slug as the container name, preserves stopped containers for later inspection, writes one structured BDI log per task, and keeps resumable progress in `tac-state.json`.

```bash
uv run python theagentcompany/run_tac_bdi.py \
  --tasks-file theagentcompany/tac-tasks.md \
  --structured-log-dir theagentcompany/tac-structured-logs \
  --state-file theagentcompany/tac-state.json \
  --verbose
```

Run the same command again to resume from the saved `executed_tasks` and `missing_tasks`.

## Useful flags

- `--provider codex|native` (default `codex`)
- `--model <name>`
- `--max-cycles <n>`
- `--log-file <path>`
- `--structured-log-file <path>` for manual or single-task runs
- `--structured-log-dir <path>` for managed per-task JSON logs
- `--state-file <path>` for resumable batch progress
- `--server-hostname <host>` for `/utils/init.sh`
- `--init-timeout <seconds>`

## Notes

- The agent follows TAC Step 2.3 behavior by treating the task as: `Complete the task in /instruction/task.md`.
- The script executes commands in the container via `docker exec <container> /bin/bash -lc ...`.
- In managed modes, `--verbose` now streams `/utils/init.sh` output live while the runner is waiting for readiness.
- If startup fails in managed mode, the runner prints the failure details immediately and leaves the failed container available for manual inspection.
- `docker logs` is not always sufficient for startup debugging here because `/utils/init.sh` runs through `docker exec`, so the most useful output is the streamed init output.
- In managed batch mode, successfully completed containers are stopped after each run but not removed.
- If a task container name already exists from an older run, it is renamed to `<slug>--prev-<timestamp>` before the new run starts.
