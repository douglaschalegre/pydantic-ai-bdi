"""Base agent interface for benchmark comparisons."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class Tool:
    """Represents a tool available to agents."""

    name: str
    description: str
    function: Any
    parameters: Dict[str, Any]


@dataclass
class AgentExecutionResult:
    """Result of agent execution."""

    success: bool
    final_state: Dict[str, Any]
    execution_log: str
    error_message: Optional[str] = None

    # Metrics
    steps_executed: int = 0
    cycles_completed: int = 0  # BDI-specific
    tokens_used_input: int = 0
    tokens_used_output: int = 0
    api_calls_made: int = 0


class BaseAgent(ABC):
    """Base interface for all agent implementations."""

    def __init__(
        self,
        model_name: str = "gpt-4",
        verbose: bool = False,
        timeout_seconds: float = 600.0,
    ):
        self.model_name = model_name
        self.verbose = verbose
        self.timeout_seconds = timeout_seconds
        self.tools: List[Tool] = []

    @abstractmethod
    async def execute_task(
        self,
        goal: str,
        initial_context: Dict[str, Any],
        tools_available: List[str],
    ) -> AgentExecutionResult:
        """Execute a task and return results.

        Args:
            goal: The high-level goal to achieve
            initial_context: Initial context/information
            tools_available: List of tool names available

        Returns:
            AgentExecutionResult with success status and metrics
        """
        pass

    @abstractmethod
    def register_tools(self, tools: List[Tool]):
        """Register tools that the agent can use.

        Args:
            tools: List of Tool objects
        """
        pass

    @abstractmethod
    def get_framework_name(self) -> str:
        """Get the name of the agent framework.

        Returns:
            Framework name (e.g., "BDI", "LangGraph", "CrewAI")
        """
        pass

    def get_model_name(self) -> str:
        """Get the model name being used."""
        return self.model_name

    @abstractmethod
    def get_lines_of_code_required(self) -> int:
        """Get approximate lines of code required to set up this agent.

        This is a usability metric - simpler frameworks require less code.

        Returns:
            Approximate LOC required for typical task setup
        """
        pass

    @abstractmethod
    def get_complexity_score(self) -> float:
        """Get subjective complexity score for using this framework.

        Scale: 1.0 (very simple) to 10.0 (very complex)

        Returns:
            Complexity score
        """
        pass

    def supports_human_in_the_loop(self) -> bool:
        """Whether this framework supports human-in-the-loop intervention."""
        return False

    def supports_belief_tracking(self) -> bool:
        """Whether this framework explicitly tracks beliefs/knowledge."""
        return False

    def supports_plan_reconsideration(self) -> bool:
        """Whether this framework supports dynamic plan reconsideration."""
        return False


# Common tools for all agents

def read_file_tool(file_path: str) -> str:
    """Read a file from filesystem."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"


def write_file_tool(file_path: str, content: str) -> str:
    """Write content to a file."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Error writing file: {e}"


def list_directory_tool(path: str = ".") -> str:
    """List contents of a directory."""
    import os
    try:
        items = os.listdir(path)
        return "\n".join(items)
    except Exception as e:
        return f"Error listing directory: {e}"


def run_shell_command_tool(command: str) -> str:
    """Run a shell command (with safety restrictions)."""
    import subprocess

    # Safety: Only allow certain safe commands
    safe_commands = ['ls', 'git', 'pwd', 'echo', 'cat', 'grep', 'find', 'wc']

    cmd_name = command.strip().split()[0] if command.strip() else ""

    if cmd_name not in safe_commands:
        return f"Command '{cmd_name}' not allowed for security reasons"

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"
    except subprocess.TimeoutExpired:
        return "Command timed out"
    except Exception as e:
        return f"Error running command: {e}"


# Tool registry
STANDARD_TOOLS = {
    'read_file': Tool(
        name='read_file',
        description='Read contents of a file',
        function=read_file_tool,
        parameters={'file_path': 'str'},
    ),
    'write_file': Tool(
        name='write_file',
        description='Write content to a file',
        function=write_file_tool,
        parameters={'file_path': 'str', 'content': 'str'},
    ),
    'list_directory': Tool(
        name='list_directory',
        description='List contents of a directory',
        function=list_directory_tool,
        parameters={'path': 'str'},
    ),
    'run_shell_command': Tool(
        name='run_shell_command',
        description='Run a shell command',
        function=run_shell_command_tool,
        parameters={'command': 'str'},
    ),
}


def get_tools_by_names(tool_names: List[str]) -> List[Tool]:
    """Get Tool objects by their names."""
    return [STANDARD_TOOLS[name] for name in tool_names if name in STANDARD_TOOLS]
