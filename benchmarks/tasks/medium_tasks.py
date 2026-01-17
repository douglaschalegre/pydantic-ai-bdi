"""Medium complexity task definitions (4-10 steps, 2-10 minutes)."""

from .task_schema import TaskCategory, TaskDomain, TaskDefinition, SuccessCriteria

MEDIUM_TASKS = [
    TaskDefinition(
        id="medium_code_analysis",
        name="Analyze Code Structure",
        description="Analyze Python codebase structure and generate summary",
        category=TaskCategory.MEDIUM,
        domain=TaskDomain.CODE_ANALYSIS,
        tags=["python", "analysis", "documentation"],
        goal="Analyze the bdi/ directory structure, count files, classes, and functions, and create a summary report",
        initial_context={
            "directory": "bdi/",
            "output_file": "code_structure_report.md"
        },
        tools_available=["list_directory", "read_file", "write_file"],
        success_criteria=[
            SuccessCriteria(
                description="All Python files found and analyzed",
                validator="all_files_analyzed",
                validator_params={"directory": "bdi/"}
            ),
            SuccessCriteria(
                description="Report file created",
                validator="file_exists",
                validator_params={"file_path": "code_structure_report.md"}
            ),
            SuccessCriteria(
                description="Report contains accurate counts",
                validator="report_contains_counts",
                validator_params={"required_fields": ["files", "classes", "functions"]}
            ),
        ],
        expected_min_steps=4,
        expected_max_steps=8,
        expected_time_seconds=120.0,
        timeout_seconds=300.0,
        difficulty_score=5.0,
        requires_file_system=True,
        teardown_function="cleanup_report_file",
    ),

    TaskDefinition(
        id="medium_dependency_extraction",
        name="Extract Project Dependencies",
        description="Extract all dependencies from project and categorize them",
        category=TaskCategory.MEDIUM,
        domain=TaskDomain.CODE_ANALYSIS,
        tags=["dependencies", "python", "analysis"],
        goal="Read pyproject.toml, extract all dependencies, categorize them (main/dev), and create a JSON report",
        initial_context={
            "config_file": "pyproject.toml",
            "output_file": "dependencies_report.json"
        },
        tools_available=["read_file", "write_file"],
        success_criteria=[
            SuccessCriteria(
                description="pyproject.toml parsed successfully",
                validator="toml_parsed",
                validator_params={"file_path": "pyproject.toml"}
            ),
            SuccessCriteria(
                description="Dependencies extracted",
                validator="dependencies_extracted",
                validator_params={"min_dependencies": 3}
            ),
            SuccessCriteria(
                description="JSON report created",
                validator="valid_json_file",
                validator_params={"file_path": "dependencies_report.json"}
            ),
        ],
        expected_min_steps=4,
        expected_max_steps=7,
        expected_time_seconds=90.0,
        timeout_seconds=200.0,
        difficulty_score=4.5,
        requires_file_system=True,
        teardown_function="cleanup_dependencies_report",
    ),

    TaskDefinition(
        id="medium_log_analysis",
        name="Analyze Log File Patterns",
        description="Analyze a log file and extract error patterns",
        category=TaskCategory.MEDIUM,
        domain=TaskDomain.DATA_PROCESSING,
        tags=["logs", "analysis", "patterns"],
        goal="Read bdi_agent_log.md (if exists, or create sample), extract all error/failure patterns, and create summary",
        initial_context={
            "log_file": "bdi_agent_log.md",
            "output_file": "log_analysis_report.txt"
        },
        tools_available=["read_file", "write_file"],
        success_criteria=[
            SuccessCriteria(
                description="Log file analyzed",
                validator="file_was_read",
                validator_params={"file_path": "bdi_agent_log.md"}
            ),
            SuccessCriteria(
                description="Error patterns identified",
                validator="patterns_identified",
                validator_params={}
            ),
            SuccessCriteria(
                description="Analysis report created",
                validator="file_exists",
                validator_params={"file_path": "log_analysis_report.txt"}
            ),
        ],
        expected_min_steps=5,
        expected_max_steps=8,
        expected_time_seconds=100.0,
        timeout_seconds=250.0,
        difficulty_score=5.5,
        requires_file_system=True,
        setup_function="ensure_log_file_exists",
        teardown_function="cleanup_log_analysis",
    ),

    TaskDefinition(
        id="medium_refactor_imports",
        name="Refactor Import Statements",
        description="Find and standardize import statements across multiple files",
        category=TaskCategory.MEDIUM,
        domain=TaskDomain.CODE_ANALYSIS,
        tags=["refactoring", "python", "imports"],
        goal="Analyze all Python files in bdi/schemas/, identify import patterns, and create refactoring recommendations",
        initial_context={
            "directory": "bdi/schemas/",
            "output_file": "import_analysis.md"
        },
        tools_available=["list_directory", "read_file", "write_file"],
        success_criteria=[
            SuccessCriteria(
                description="All schema files analyzed",
                validator="all_files_analyzed",
                validator_params={"directory": "bdi/schemas/"}
            ),
            SuccessCriteria(
                description="Import patterns identified",
                validator="imports_identified",
                validator_params={}
            ),
            SuccessCriteria(
                description="Recommendations document created",
                validator="file_exists",
                validator_params={"file_path": "import_analysis.md"}
            ),
        ],
        expected_min_steps=6,
        expected_max_steps=10,
        expected_time_seconds=150.0,
        timeout_seconds=300.0,
        difficulty_score=6.0,
        requires_file_system=True,
        teardown_function="cleanup_import_analysis",
    ),

    TaskDefinition(
        id="medium_test_discovery",
        name="Discover Test Coverage Gaps",
        description="Identify which modules lack test files",
        category=TaskCategory.MEDIUM,
        domain=TaskDomain.CODE_ANALYSIS,
        tags=["testing", "coverage", "analysis"],
        goal="Compare bdi/ module files with tests/ (if exists) and identify untested modules",
        initial_context={
            "source_dir": "bdi/",
            "test_dir": "tests/",
            "output_file": "test_coverage_gaps.md"
        },
        tools_available=["list_directory", "read_file", "write_file"],
        success_criteria=[
            SuccessCriteria(
                description="Source files inventoried",
                validator="directory_scanned",
                validator_params={"directory": "bdi/"}
            ),
            SuccessCriteria(
                description="Coverage gaps identified",
                validator="gaps_identified",
                validator_params={}
            ),
            SuccessCriteria(
                description="Report created",
                validator="file_exists",
                validator_params={"file_path": "test_coverage_gaps.md"}
            ),
        ],
        expected_min_steps=5,
        expected_max_steps=9,
        expected_time_seconds=120.0,
        timeout_seconds=250.0,
        difficulty_score=5.0,
        requires_file_system=True,
        teardown_function="cleanup_coverage_report",
    ),

    TaskDefinition(
        id="medium_git_history_summary",
        name="Summarize Git Commit History",
        description="Analyze recent git commits and categorize changes",
        category=TaskCategory.MEDIUM,
        domain=TaskDomain.CODE_ANALYSIS,
        tags=["git", "history", "analysis"],
        goal="Get last 20 commits, categorize by type (feat/fix/docs), and create summary report",
        initial_context={
            "commit_count": 20,
            "output_file": "git_history_summary.md"
        },
        tools_available=["run_shell_command", "write_file"],
        success_criteria=[
            SuccessCriteria(
                description="Git history retrieved",
                validator="git_log_retrieved",
                validator_params={"min_commits": 10}
            ),
            SuccessCriteria(
                description="Commits categorized",
                validator="commits_categorized",
                validator_params={}
            ),
            SuccessCriteria(
                description="Summary report created",
                validator="file_exists",
                validator_params={"file_path": "git_history_summary.md"}
            ),
        ],
        expected_min_steps=4,
        expected_max_steps=7,
        expected_time_seconds=100.0,
        timeout_seconds=200.0,
        difficulty_score=5.0,
        requires_file_system=True,
        teardown_function="cleanup_git_summary",
    ),

    TaskDefinition(
        id="medium_data_pipeline",
        name="Create Data Processing Pipeline",
        description="Read CSV, transform data, and output JSON",
        category=TaskCategory.MEDIUM,
        domain=TaskDomain.DATA_PROCESSING,
        tags=["data", "pipeline", "transformation"],
        goal="Create sample CSV file, read it, transform data (uppercase names, filter by condition), output as JSON",
        initial_context={
            "input_format": "csv",
            "output_format": "json",
            "transformation": "uppercase_names_and_filter"
        },
        tools_available=["write_file", "read_file"],
        success_criteria=[
            SuccessCriteria(
                description="Sample CSV created",
                validator="file_exists",
                validator_params={"file_path": "sample_data.csv"}
            ),
            SuccessCriteria(
                description="Data transformed correctly",
                validator="data_transformed",
                validator_params={}
            ),
            SuccessCriteria(
                description="JSON output valid",
                validator="valid_json_file",
                validator_params={"file_path": "transformed_data.json"}
            ),
        ],
        expected_min_steps=5,
        expected_max_steps=8,
        expected_time_seconds=120.0,
        timeout_seconds=250.0,
        difficulty_score=5.5,
        requires_file_system=True,
        teardown_function="cleanup_pipeline_files",
    ),

    TaskDefinition(
        id="medium_documentation_generation",
        name="Generate API Documentation",
        description="Extract docstrings and generate API documentation",
        category=TaskCategory.MEDIUM,
        domain=TaskDomain.CODE_ANALYSIS,
        tags=["documentation", "python", "api"],
        goal="Read bdi/agent.py, extract all class and method docstrings, and generate formatted API docs",
        initial_context={
            "source_file": "bdi/agent.py",
            "output_file": "api_documentation.md"
        },
        tools_available=["read_file", "write_file"],
        success_criteria=[
            SuccessCriteria(
                description="Source file analyzed",
                validator="file_was_read",
                validator_params={"file_path": "bdi/agent.py"}
            ),
            SuccessCriteria(
                description="Docstrings extracted",
                validator="docstrings_extracted",
                validator_params={"min_docstrings": 3}
            ),
            SuccessCriteria(
                description="Documentation file created",
                validator="file_exists",
                validator_params={"file_path": "api_documentation.md"}
            ),
        ],
        expected_min_steps=4,
        expected_max_steps=7,
        expected_time_seconds=110.0,
        timeout_seconds=250.0,
        difficulty_score=5.5,
        requires_file_system=True,
        teardown_function="cleanup_api_docs",
    ),
]
