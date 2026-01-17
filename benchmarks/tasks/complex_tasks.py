"""Complex task definitions (10+ steps, >10 minutes)."""

from .task_schema import TaskCategory, TaskDomain, TaskDefinition, SuccessCriteria

COMPLEX_TASKS = [
    TaskDefinition(
        id="complex_codebase_audit",
        name="Complete Codebase Security Audit",
        description="Comprehensive security audit of the entire codebase",
        category=TaskCategory.COMPLEX,
        domain=TaskDomain.CODE_ANALYSIS,
        tags=["security", "audit", "comprehensive"],
        goal="Scan entire codebase for security issues: hardcoded secrets, SQL injection risks, XSS vulnerabilities, insecure dependencies, and generate detailed report",
        initial_context={
            "directories": ["bdi/", "server/", "helper/"],
            "output_file": "security_audit_report.md"
        },
        tools_available=["list_directory", "read_file", "write_file"],
        success_criteria=[
            SuccessCriteria(
                description="All directories scanned",
                validator="all_directories_scanned",
                validator_params={"directories": ["bdi/", "server/", "helper/"]}
            ),
            SuccessCriteria(
                description="Security patterns checked",
                validator="security_patterns_checked",
                validator_params={"patterns": ["password", "api_key", "eval(", "exec("]}
            ),
            SuccessCriteria(
                description="Comprehensive report generated",
                validator="comprehensive_report",
                validator_params={"file_path": "security_audit_report.md", "min_sections": 4}
            ),
        ],
        expected_min_steps=12,
        expected_max_steps=20,
        expected_time_seconds=600.0,
        timeout_seconds=900.0,
        difficulty_score=8.5,
        requires_file_system=True,
        teardown_function="cleanup_security_audit",
    ),

    TaskDefinition(
        id="complex_refactoring_plan",
        name="Create Comprehensive Refactoring Plan",
        description="Analyze codebase and create detailed refactoring plan",
        category=TaskCategory.COMPLEX,
        domain=TaskDomain.CODE_ANALYSIS,
        tags=["refactoring", "architecture", "planning"],
        goal="Analyze bdi/ codebase for: code duplication, long functions, high complexity, missing type hints, and create prioritized refactoring plan with effort estimates",
        initial_context={
            "directory": "bdi/",
            "output_file": "refactoring_plan.md"
        },
        tools_available=["list_directory", "read_file", "write_file"],
        success_criteria=[
            SuccessCriteria(
                description="Code quality issues identified",
                validator="quality_issues_found",
                validator_params={"min_issues": 5}
            ),
            SuccessCriteria(
                description="Duplication analysis performed",
                validator="duplication_analyzed",
                validator_params={}
            ),
            SuccessCriteria(
                description="Prioritized plan created",
                validator="prioritized_plan_created",
                validator_params={"file_path": "refactoring_plan.md"}
            ),
        ],
        expected_min_steps=15,
        expected_max_steps=25,
        expected_time_seconds=700.0,
        timeout_seconds=1000.0,
        difficulty_score=9.0,
        requires_file_system=True,
        teardown_function="cleanup_refactoring_plan",
    ),
]
