# TAC BDI Agent Runner

This folder contains a BDI-based runner for TheAgentCompany tasks inside a Docker task container (default: `tac-test`).

The runner creates a `BDI` agent with tools to:
- Read `/instruction/task.md` from the task container
- Run arbitrary shell commands in the container
- Inspect `/workspace`, `/instruction`, and `/utils`
- Optionally run `/utils/eval.py`

## Prerequisites

1. TAC infra containers are running.
2. Your task container exists and is running (e.g. `tac-test`).
3. You already initialized the task at least once:

```bash
docker exec tac-test /bin/bash -lc 'SERVER_HOSTNAME=127.0.0.1 bash /utils/init.sh'
```

4. Python dependencies are installed in repo root:

```bash
cd /Users/douglas/code/masters/pydantic-ai-bdi
uv sync
```

## Run

From repo root:

```bash
uv run python the-agent-company/run_tac_bdi.py --container tac-test --verbose
```

Useful flags:
- `--provider codex|native` (default `codex`)
- `--model <name>`
- `--max-cycles <n>`
- `--include-playwright` (attach Playwright MCP server for browser-heavy tasks)
- `--log-file <path>`

Example with Playwright:

```bash
uv run python the-agent-company/run_tac_bdi.py \
  --container tac-test \
  --include-playwright \
  --verbose
```

## Notes

- The agent follows TAC Step 2.3 behavior by treating the task as: `Complete the task in /instruction/task.md`.
- The script executes commands in the container via `docker exec <container> /bin/bash -lc ...`.
- If you evaluate at the end, ensure required env vars are available for `/utils/eval.py` (`LITELLM_*`, `DECRYPTION_KEY`).
