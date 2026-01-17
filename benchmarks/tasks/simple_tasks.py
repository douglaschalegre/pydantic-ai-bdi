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
        id="simple_file_search",
        name="Find Python Files",
        description="Search for all Python files in a specific directory",
        category=TaskCategory.SIMPLE,
        domain=TaskDomain.FILE_OPS,
        tags=["filesystem", "search"],
        goal="Find all .py files in the bdi/ directory and list them",
        initial_context={
            "directory": "bdi/",
            "file_extension": ".py"
        },
        tools_available=["list_directory", "read_file"],
        success_criteria=[
            SuccessCriteria(
                description="All Python files found",
                validator="all_python_files_found",
                validator_params={"directory": "bdi/"}
            ),
            SuccessCriteria(
                description="No false positives (non-.py files)",
                validator="no_false_positives",
                validator_params={"extension": ".py"}
            ),
        ],
        expected_min_steps=1,
        expected_max_steps=3,
        expected_time_seconds=15.0,
        timeout_seconds=60.0,
        difficulty_score=2.0,
        requires_file_system=True,
    ),

    TaskDefinition(
        id="simple_json_parse",
        name="Parse JSON Configuration",
        description="Read and parse a JSON file, extract specific field",
        category=TaskCategory.SIMPLE,
        domain=TaskDomain.DATA_PROCESSING,
        tags=["json", "parsing"],
        goal="Read package.json (if exists) or create test JSON file, parse it, and extract the 'name' field",
        initial_context={
            "task": "parse JSON and extract name field"
        },
        tools_available=["read_file", "write_file"],
        success_criteria=[
            SuccessCriteria(
                description="JSON file was read and parsed",
                validator="json_parsed_successfully",
                validator_params={}
            ),
            SuccessCriteria(
                description="Correct field extracted",
                validator="field_extracted",
                validator_params={"field_name": "name"}
            ),
        ],
        expected_min_steps=1,
        expected_max_steps=3,
        expected_time_seconds=15.0,
        timeout_seconds=60.0,
        difficulty_score=2.0,
        requires_file_system=True,
    ),

    TaskDefinition(
        id="simple_text_transform",
        name="Convert Text to Uppercase",
        description="Read a file and create a new file with all text in uppercase",
        category=TaskCategory.SIMPLE,
        domain=TaskDomain.DATA_PROCESSING,
        tags=["text", "transformation"],
        goal="Read README.md, convert all text to uppercase, and save to README_UPPER.md",
        initial_context={
            "input_file": "README.md",
            "output_file": "README_UPPER.md",
            "transformation": "uppercase"
        },
        tools_available=["read_file", "write_file"],
        success_criteria=[
            SuccessCriteria(
                description="Output file created",
                validator="file_exists",
                validator_params={"file_path": "README_UPPER.md"}
            ),
            SuccessCriteria(
                description="Text converted to uppercase",
                validator="text_is_uppercase",
                validator_params={"file_path": "README_UPPER.md"}
            ),
        ],
        expected_min_steps=2,
        expected_max_steps=3,
        expected_time_seconds=20.0,
        timeout_seconds=60.0,
        difficulty_score=2.5,
        requires_file_system=True,
        setup_function="ensure_readme_exists",
        teardown_function="cleanup_uppercase_file",
    ),

    TaskDefinition(
        id="simple_git_status",
        name="Check Git Status",
        description="Check the current git repository status",
        category=TaskCategory.SIMPLE,
        domain=TaskDomain.CODE_ANALYSIS,
        tags=["git", "version-control"],
        goal="Determine the current git branch and whether there are uncommitted changes",
        initial_context={
            "repository_path": "."
        },
        tools_available=["run_shell_command", "read_file"],
        success_criteria=[
            SuccessCriteria(
                description="Current branch identified",
                validator="branch_identified",
                validator_params={}
            ),
            SuccessCriteria(
                description="Clean/dirty status determined",
                validator="status_determined",
                validator_params={}
            ),
        ],
        expected_min_steps=1,
        expected_max_steps=2,
        expected_time_seconds=10.0,
        timeout_seconds=60.0,
        difficulty_score=2.0,
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

    TaskDefinition(
        id="simple_create_directory",
        name="Create Directory Structure",
        description="Create a new directory with subdirectories",
        category=TaskCategory.SIMPLE,
        domain=TaskDomain.FILE_OPS,
        tags=["filesystem", "creation"],
        goal="Create a test directory structure: test_dir/subdir1 and test_dir/subdir2",
        initial_context={
            "base_dir": "test_dir",
            "subdirs": ["subdir1", "subdir2"]
        },
        tools_available=["run_shell_command", "list_directory"],
        success_criteria=[
            SuccessCriteria(
                description="Base directory created",
                validator="directory_exists",
                validator_params={"path": "test_dir"}
            ),
            SuccessCriteria(
                description="Subdirectories created",
                validator="subdirectories_exist",
                validator_params={"base": "test_dir", "subdirs": ["subdir1", "subdir2"]}
            ),
        ],
        expected_min_steps=1,
        expected_max_steps=3,
        expected_time_seconds=15.0,
        timeout_seconds=60.0,
        difficulty_score=2.0,
        requires_file_system=True,
        teardown_function="cleanup_test_directory",
    ),

    TaskDefinition(
        id="simple_word_count",
        name="Count Words in File",
        description="Count total words in a text file",
        category=TaskCategory.SIMPLE,
        domain=TaskDomain.DATA_PROCESSING,
        tags=["text", "analysis"],
        goal="Count the total number of words in README.md",
        initial_context={
            "file_path": "README.md"
        },
        tools_available=["read_file"],
        success_criteria=[
            SuccessCriteria(
                description="File was read",
                validator="file_was_read",
                validator_params={"file_path": "README.md"}
            ),
            SuccessCriteria(
                description="Word count is reasonably accurate",
                validator="word_count_accurate",
                validator_params={"file_path": "README.md", "tolerance_percent": 5.0}
            ),
        ],
        expected_min_steps=1,
        expected_max_steps=2,
        expected_time_seconds=15.0,
        timeout_seconds=60.0,
        difficulty_score=1.5,
        requires_file_system=True,
    ),
]
