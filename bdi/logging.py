"""Logging and state formatting utilities for the BDI agent.

This module provides functions for logging agent state to files and console,
and for formatting beliefs, desires, and intentions for display or LLM prompts.
"""

from typing import TYPE_CHECKING, Literal
from datetime import datetime
from helper.util import bcolors

if TYPE_CHECKING:
    from bdi.agent import BDI


def write_to_log_file(agent: "BDI", content: str, section_title: str = None) -> None:
    """Write content to the markdown log file.

    Args:
        agent: The BDI agent instance
        content: Content to write to the log file
        section_title: Optional section title for markdown formatting
    """
    if not agent.log_file_path:
        return

    try:
        with open(agent.log_file_path, "a", encoding="utf-8") as f:
            if section_title:
                f.write(f"## {section_title}\n\n")
            f.write(content)
            f.write("\n\n")
    except Exception as e:
        print(f"{bcolors.FAIL}Failed to write to log file: {e}{bcolors.ENDC}")


def format_beliefs_for_context(agent: "BDI") -> str:
    """Format current beliefs for inclusion in LLM prompts.

    Args:
        agent: The BDI agent instance

    Returns:
        Formatted string containing all beliefs with their values and certainty
    """
    if not agent.beliefs.beliefs:
        return "No beliefs recorded yet."

    beliefs_lines = []
    for name, belief in agent.beliefs.beliefs.items():
        beliefs_lines.append(
            f"- {name}: {belief.value} (Certainty: {belief.certainty:.2f})"
        )
    return "\n".join(beliefs_lines)


def log_states(
    agent: "BDI",
    types: list[Literal["beliefs", "desires", "intentions"]],
    message: str | None = None,
) -> None:
    """Log current agent state to console and file.

    Args:
        agent: The BDI agent instance
        types: List of state types to log (beliefs, desires, intentions)
        message: Optional message to display with the state
    """
    if message:
        print(f"{bcolors.SYSTEM}{message}{bcolors.ENDC}")

    # Prepare markdown content for file logging
    md_content = []
    if message:
        md_content.append(f"**{message}**\n")
    md_content.append(f"*Timestamp: {datetime.now().isoformat()}*\n")

    if "beliefs" in types:
        if agent.verbose:
            belief_str = "\n".join(
                [
                    f"  - {name}: {b.value} (Source: {b.source}, Certainty: {b.certainty:.2f}, Time: {datetime.fromtimestamp(b.timestamp).isoformat()})"
                    for name, b in agent.beliefs.beliefs.items()
                ]
            )
            print(
                f"{bcolors.BELIEF}Beliefs:\n{belief_str or '  (None)'}{bcolors.ENDC}"
            )
        else:
            print(
                f"{bcolors.BELIEF}Beliefs: {len(agent.beliefs.beliefs)} items{bcolors.ENDC}"
            )

        # Add to markdown
        md_content.append("### Beliefs\n")
        if agent.beliefs.beliefs:
            for name, b in agent.beliefs.beliefs.items():
                md_content.append(
                    f"- **{name}**: {b.value} (Source: {b.source}, Certainty: {b.certainty:.2f}, Time: {datetime.fromtimestamp(b.timestamp).isoformat()})\n"
                )
        else:
            md_content.append("*(None)*\n")

    if "desires" in types:
        if agent.verbose:
            desire_str = "\n".join(
                [
                    f"  - {d.id}: {d.description} (Status: {d.status.value}, Priority: {d.priority})"
                    for d in agent.desires
                ]
            )
            print(
                f"{bcolors.DESIRE}Desires:\n{desire_str or '  (None)'}{bcolors.ENDC}"
            )
        else:
            print(
                f"{bcolors.DESIRE}Desires: {len(agent.desires)} items{bcolors.ENDC}"
            )

        # Add to markdown
        md_content.append("### Desires\n")
        if agent.desires:
            for d in agent.desires:
                md_content.append(
                    f"- **{d.id}**: {d.description} (Status: {d.status.value}, Priority: {d.priority})\n"
                )
        else:
            md_content.append("*(None)*\n")

    if "intentions" in types:
        if agent.verbose:
            intention_str = "\n".join(
                [
                    f"  - Desire '{i.desire_id}': Next -> {i.steps[i.current_step].description if i.current_step < len(i.steps) else '(Completed)'} (Step {i.current_step + 1}/{len(i.steps)})"
                    for i in agent.intentions
                ]
            )
            print(
                f"{bcolors.INTENTION}Intentions:\n{intention_str or '  (None)'}{bcolors.ENDC}"
            )
        else:
            print(
                f"{bcolors.INTENTION}Intentions: {len(agent.intentions)} items{bcolors.ENDC}"
            )

        # Add to markdown
        md_content.append("### Intentions\n")
        if agent.intentions:
            for i in agent.intentions:
                next_step = (
                    i.steps[i.current_step].description
                    if i.current_step < len(i.steps)
                    else "(Completed)"
                )
                md_content.append(
                    f"- **Desire '{i.desire_id}'**: Next → {next_step} (Step {i.current_step + 1}/{len(i.steps)})\n"
                )
        else:
            md_content.append("*(None)*\n")

    # Write to log file if enabled
    if agent.log_file_path:
        write_to_log_file(agent, "".join(md_content))


__all__ = [
    "write_to_log_file",
    "format_beliefs_for_context",
    "log_states",
]
