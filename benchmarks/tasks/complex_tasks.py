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

    TaskDefinition(
        id="complex_test_suite_generation",
        name="Generate Complete Test Suite",
        description="Generate comprehensive test suite for a module",
        category=TaskCategory.COMPLEX,
        domain=TaskDomain.CODE_ANALYSIS,
        tags=["testing", "generation", "quality"],
        goal="Analyze bdi/agent.py, generate comprehensive test suite with unit tests, integration tests, edge cases, and mocks",
        initial_context={
            "source_file": "bdi/agent.py",
            "output_file": "test_agent_generated.py"
        },
        tools_available=["read_file", "write_file"],
        success_criteria=[
            SuccessCriteria(
                description="Source code analyzed",
                validator="file_was_read",
                validator_params={"file_path": "bdi/agent.py"}
            ),
            SuccessCriteria(
                description="Test file created with valid Python",
                validator="valid_python_file",
                validator_params={"file_path": "test_agent_generated.py"}
            ),
            SuccessCriteria(
                description="Multiple test cases generated",
                validator="multiple_test_cases",
                validator_params={"file_path": "test_agent_generated.py", "min_tests": 8}
            ),
            SuccessCriteria(
                description="Edge cases covered",
                validator="edge_cases_covered",
                validator_params={}
            ),
        ],
        expected_min_steps=10,
        expected_max_steps=18,
        expected_time_seconds=500.0,
        timeout_seconds=800.0,
        difficulty_score=8.0,
        requires_file_system=True,
        teardown_function="cleanup_generated_tests",
    ),

    TaskDefinition(
        id="complex_dependency_upgrade_plan",
        name="Create Dependency Upgrade Strategy",
        description="Analyze dependencies and create safe upgrade plan",
        category=TaskCategory.COMPLEX,
        domain=TaskDomain.CODE_ANALYSIS,
        tags=["dependencies", "upgrades", "planning"],
        goal="Read pyproject.toml, identify outdated dependencies, check for breaking changes, analyze impact, and create phased upgrade plan",
        initial_context={
            "config_file": "pyproject.toml",
            "output_file": "dependency_upgrade_plan.md"
        },
        tools_available=["read_file", "write_file", "run_shell_command"],
        success_criteria=[
            SuccessCriteria(
                description="Dependencies analyzed",
                validator="dependencies_analyzed",
                validator_params={}
            ),
            SuccessCriteria(
                description="Impact assessment performed",
                validator="impact_assessed",
                validator_params={}
            ),
            SuccessCriteria(
                description="Phased plan created",
                validator="phased_plan_created",
                validator_params={"file_path": "dependency_upgrade_plan.md", "min_phases": 2}
            ),
        ],
        expected_min_steps=12,
        expected_max_steps=20,
        expected_time_seconds=600.0,
        timeout_seconds=900.0,
        difficulty_score=8.5,
        requires_file_system=True,
        requires_external_api=True,  # May need to check package versions
        teardown_function="cleanup_upgrade_plan",
    ),

    TaskDefinition(
        id="complex_architecture_documentation",
        name="Generate Architecture Documentation",
        description="Create comprehensive architecture documentation from codebase",
        category=TaskCategory.COMPLEX,
        domain=TaskDomain.CODE_ANALYSIS,
        tags=["documentation", "architecture", "comprehensive"],
        goal="Analyze entire project structure, identify components, dependencies, data flow, and generate architecture documentation with diagrams (Mermaid syntax)",
        initial_context={
            "project_root": ".",
            "output_file": "architecture_documentation.md"
        },
        tools_available=["list_directory", "read_file", "write_file"],
        success_criteria=[
            SuccessCriteria(
                description="All major components identified",
                validator="components_identified",
                validator_params={"min_components": 5}
            ),
            SuccessCriteria(
                description="Dependencies mapped",
                validator="dependencies_mapped",
                validator_params={}
            ),
            SuccessCriteria(
                description="Architecture doc with diagrams created",
                validator="architecture_doc_with_diagrams",
                validator_params={"file_path": "architecture_documentation.md"}
            ),
        ],
        expected_min_steps=18,
        expected_max_steps=30,
        expected_time_seconds=800.0,
        timeout_seconds=1200.0,
        difficulty_score=9.5,
        requires_file_system=True,
        teardown_function="cleanup_architecture_docs",
    ),

    TaskDefinition(
        id="complex_bug_hunt",
        name="Systematic Bug Discovery",
        description="Comprehensive bug hunting across codebase",
        category=TaskCategory.COMPLEX,
        domain=TaskDomain.DEBUGGING,
        tags=["debugging", "analysis", "quality"],
        goal="Scan codebase for: potential null pointer errors, race conditions, resource leaks, error handling gaps, edge case bugs, and create prioritized bug report",
        initial_context={
            "directories": ["bdi/", "server/"],
            "output_file": "bug_report.md"
        },
        tools_available=["list_directory", "read_file", "write_file"],
        success_criteria=[
            SuccessCriteria(
                description="All target files scanned",
                validator="all_files_scanned",
                validator_params={"directories": ["bdi/", "server/"]}
            ),
            SuccessCriteria(
                description="Multiple bug categories checked",
                validator="bug_categories_checked",
                validator_params={"min_categories": 4}
            ),
            SuccessCriteria(
                description="Prioritized bug report created",
                validator="prioritized_bug_report",
                validator_params={"file_path": "bug_report.md"}
            ),
        ],
        expected_min_steps=14,
        expected_max_steps=25,
        expected_time_seconds=650.0,
        timeout_seconds=1000.0,
        difficulty_score=8.5,
        requires_file_system=True,
        teardown_function="cleanup_bug_report",
    ),

    TaskDefinition(
        id="complex_performance_analysis",
        name="Performance Optimization Analysis",
        description="Comprehensive performance analysis and optimization plan",
        category=TaskCategory.COMPLEX,
        domain=TaskDomain.CODE_ANALYSIS,
        tags=["performance", "optimization", "analysis"],
        goal="Analyze codebase for: inefficient algorithms, unnecessary loops, blocking I/O, memory leaks, and create performance optimization roadmap",
        initial_context={
            "directory": "bdi/",
            "output_file": "performance_optimization_plan.md"
        },
        tools_available=["list_directory", "read_file", "write_file"],
        success_criteria=[
            SuccessCriteria(
                description="Performance hotspots identified",
                validator="hotspots_identified",
                validator_params={"min_hotspots": 3}
            ),
            SuccessCriteria(
                description="Algorithmic complexity analyzed",
                validator="complexity_analyzed",
                validator_params={}
            ),
            SuccessCriteria(
                description="Optimization roadmap created",
                validator="optimization_roadmap",
                validator_params={"file_path": "performance_optimization_plan.md"}
            ),
        ],
        expected_min_steps=12,
        expected_max_steps=22,
        expected_time_seconds=600.0,
        timeout_seconds=900.0,
        difficulty_score=8.0,
        requires_file_system=True,
        teardown_function="cleanup_performance_plan",
    ),

    TaskDefinition(
        id="complex_migration_plan",
        name="Create Framework Migration Plan",
        description="Plan migration from one framework to another",
        category=TaskCategory.COMPLEX,
        domain=TaskDomain.CODE_ANALYSIS,
        tags=["migration", "planning", "architecture"],
        goal="Analyze FastAPI server code, create plan to migrate to alternative framework (e.g., Flask), identify breaking changes, create phased migration strategy",
        initial_context={
            "source_framework": "FastAPI",
            "target_framework": "Flask",
            "directory": "server/",
            "output_file": "migration_plan.md"
        },
        tools_available=["list_directory", "read_file", "write_file"],
        success_criteria=[
            SuccessCriteria(
                description="Current framework usage analyzed",
                validator="framework_usage_analyzed",
                validator_params={"directory": "server/"}
            ),
            SuccessCriteria(
                description="Breaking changes identified",
                validator="breaking_changes_identified",
                validator_params={}
            ),
            SuccessCriteria(
                description="Phased migration plan created",
                validator="migration_plan_created",
                validator_params={"file_path": "migration_plan.md", "min_phases": 3}
            ),
        ],
        expected_min_steps=15,
        expected_max_steps=25,
        expected_time_seconds=700.0,
        timeout_seconds=1000.0,
        difficulty_score=9.0,
        requires_file_system=True,
        teardown_function="cleanup_migration_plan",
    ),
]
