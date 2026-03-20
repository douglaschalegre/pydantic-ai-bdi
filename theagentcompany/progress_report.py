from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_TASKS_FILE = Path(__file__).with_name("tac-tasks.md")
DEFAULT_STATE_FILE = Path(__file__).with_name("tac-state.json")
DEFAULT_LOG_DIR = Path(__file__).with_name("tac-structured-logs")
ACTIVE_PHASES = {
    "queued",
    "starting_container",
    "running_init",
    "ready",
    "running_agent",
}


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _task_slug_from_image(image: str) -> str:
    slug = image.strip().rsplit("/", 1)[-1].split(":", 1)[0]
    if slug.endswith("-image"):
        slug = slug[: -len("-image")]
    return slug


def _load_task_slugs(tasks_file: Path) -> list[str]:
    return [
        _task_slug_from_image(line)
        for line in tasks_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _count_tool_calls(log_path: Path) -> int:
    data = _load_json(log_path)
    if not isinstance(data, list):
        return 0

    total = 0
    for entry in data:
        if isinstance(entry, dict):
            tool_calls = entry.get("tool_calls", [])
            if isinstance(tool_calls, list):
                total += len(tool_calls)
    return total


def build_report(tasks_file: Path, state_file: Path, log_dir: Path) -> str:
    task_slugs = _load_task_slugs(tasks_file)
    state = _load_json(state_file)
    if not isinstance(state, dict):
        raise ValueError(f"Unexpected state format in {state_file}")

    successful_tasks = {
        str(task)
        for task in state.get("executed_tasks", [])
        if isinstance(task, str) and task
    }
    remaining_tasks = [
        str(task)
        for task in state.get("missing_tasks", [])
        if isinstance(task, str) and task
    ]
    current_task = state.get("current_task")
    current_phase = state.get("current_phase")

    log_paths = sorted(log_dir.glob("*.json"))
    attempted_tasks = {path.stem for path in log_paths}

    in_progress_task = None
    if (
        isinstance(current_task, str)
        and current_task
        and current_task in attempted_tasks
        and current_task not in successful_tasks
        and current_phase in ACTIVE_PHASES
    ):
        in_progress_task = current_task

    failed_tasks = attempted_tasks - successful_tasks
    if in_progress_task is not None:
        failed_tasks.discard(in_progress_task)

    executed_count = len(attempted_tasks)
    successful_count = len(successful_tasks)
    remaining_count = len(remaining_tasks)
    failed_count = len(failed_tasks)
    total_tool_calls = sum(_count_tool_calls(path) for path in log_paths)
    average_tool_calls = total_tool_calls / executed_count if executed_count else 0.0

    lines = [
        "# Experiment Progress",
        "",
        f"- Updated: {state.get('updated_at', 'unknown')}",
        f"- Total tasks: {len(task_slugs)}",
        f"- Executed tasks: {executed_count}",
        f"- Remaining tasks: {remaining_count}",
        f"- Successful tasks: {successful_count}",
        f"- Failed tasks: {failed_count}",
        f"- Average tool calls per task: {average_tool_calls:.2f}",
    ]

    if isinstance(current_task, str) and current_task:
        lines.append(f"- Current task: {current_task} ({current_phase or 'unknown'})")

    lines.extend(
        [
            "",
            "> [!note] Counting rule",
            "> Executed tasks are tasks with a structured log file. Failed tasks are attempted tasks that are not in `executed_tasks`, excluding the active in-progress task.",
        ]
    )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render the current TAC experiment progress as Obsidian markdown."
    )
    parser.add_argument("--tasks-file", type=Path, default=DEFAULT_TASKS_FILE)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional markdown output path. Prints to stdout when omitted.",
    )
    args = parser.parse_args()

    report = build_report(args.tasks_file, args.state_file, args.log_dir)
    if args.output is None:
        print(report, end="")
    else:
        args.output.write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
