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
]
