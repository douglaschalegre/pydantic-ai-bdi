"""Simple task definitions (1-3 steps, <2 minutes)."""

from .task_schema import TaskCategory, TaskDomain, TaskDefinition, SuccessCriteria

SIMPLE_TASKS = [
    TaskDefinition(
        id="simple_file_read",
        name="Read and Count Lines",
        description="Read a specific file and count the number of lines",
        category=TaskCategory.SIMPLE,
        domain=TaskDomain.FILE_OPS,
        tags=["filesystem", "basic"],
        goal="Read the pyproject.toml file and report the number of lines",
        initial_context={
            "file_path": "pyproject.toml",
            "expected_operation": "count lines"
        },
        tools_available=["read_file", "list_directory"],
        success_criteria=[
            SuccessCriteria(
                description="File was successfully read",
                validator="file_was_read",
                validator_params={"file_path": "pyproject.toml"}
            ),
            SuccessCriteria(
                description="Correct line count reported",
                validator="correct_line_count",
                validator_params={"file_path": "pyproject.toml", "tolerance": 0}
            ),
        ],
        expected_min_steps=1,
        expected_max_steps=2,
        expected_time_seconds=10.0,
        timeout_seconds=60.0,
        difficulty_score=1.0,
        requires_file_system=True,
    ),

    TaskDefinition(
        id="simple_count_functions",
        name="Count Functions in File",
        description="Count the number of function definitions in a Python file",
        category=TaskCategory.SIMPLE,
        domain=TaskDomain.CODE_ANALYSIS,
        tags=["python", "analysis"],
        goal="Count how many functions are defined in bdi/agent.py",
        initial_context={
            "file_path": "bdi/agent.py",
            "pattern": "def "
        },
        tools_available=["read_file"],
        success_criteria=[
            SuccessCriteria(
                description="File was analyzed",
                validator="file_was_read",
                validator_params={"file_path": "bdi/agent.py"}
            ),
            SuccessCriteria(
                description="Function count is accurate",
                validator="function_count_accurate",
                validator_params={"file_path": "bdi/agent.py", "tolerance": 1}
            ),
        ],
        expected_min_steps=1,
        expected_max_steps=2,
        expected_time_seconds=15.0,
        timeout_seconds=60.0,
        difficulty_score=2.5,
        requires_file_system=True,
    ),
]
