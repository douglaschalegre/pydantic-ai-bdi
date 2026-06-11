from __future__ import annotations

from pathlib import Path
import subprocess

from sbench_toy.config import COMMAND_TIMEOUT_SECONDS


def run_command(
    task_path: Path,
    command: str,
    timeout_seconds: int | None = None,
    *,
    max_timeout_seconds: int = COMMAND_TIMEOUT_SECONDS,
) -> str:
    """Run a shell command starting in the task folder."""

    if not command.strip():
        return "Command cannot be empty."

    try:
        requested_timeout = (
            max_timeout_seconds if timeout_seconds is None else int(timeout_seconds)
        )
        timeout = max(1, min(requested_timeout, max_timeout_seconds))
    except (TypeError, ValueError):
        timeout = max_timeout_seconds

    try:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=str(task_path),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        output = "\n".join(part.strip() for part in (stdout, stderr) if part).strip()
        if output:
            return f"Command timed out after {timeout} seconds.\n{output}"
        return f"Command timed out after {timeout} seconds."
    except Exception as exc:
        return f"Command failed to start: {exc}"

    output_parts = []
    if completed.stdout:
        output_parts.append(completed.stdout.strip())
    if completed.stderr:
        output_parts.append(f"[stderr]\n{completed.stderr.strip()}")
    output = "\n".join(output_parts).strip() or "(no output)"

    if completed.returncode == 0:
        return output
    return f"Command exited with code {completed.returncode}.\n{output}"
