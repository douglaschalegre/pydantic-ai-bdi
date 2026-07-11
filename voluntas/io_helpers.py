"""Small input-related helpers for CLI interactions."""

_EXIT_COMMANDS = {"quit", "exit", "q"}


def is_exit_command(value: str) -> bool:
    """Return True when user input indicates the process should exit."""
    return value.strip().lower() in _EXIT_COMMANDS


__all__ = [
    "is_exit_command",
]
