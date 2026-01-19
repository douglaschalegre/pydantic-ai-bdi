"""Setup and teardown functions for benchmark tasks."""

import os
import shutil
from pathlib import Path


def ensure_readme_exists():
    """Ensure README.md exists."""
    if not os.path.exists("README.md"):
        with open("README.md", 'w') as f:
            f.write("# Sample README\n\nThis is a test file.\n")


def cleanup_uppercase_file():
    """Remove uppercase README file."""
    if os.path.exists("README_UPPER.md"):
        os.remove("README_UPPER.md")


def cleanup_test_directory():
    """Remove test directory."""
    if os.path.exists("test_dir"):
        shutil.rmtree("test_dir")


def cleanup_report_file():
    """Remove code structure report."""
    if os.path.exists("code_structure_report.md"):
        os.remove("code_structure_report.md")


def cleanup_dependencies_report():
    """Remove dependencies report."""
    if os.path.exists("dependencies_report.json"):
        os.remove("dependencies_report.json")


def ensure_log_file_exists():
    """Ensure log file exists for analysis."""
    if not os.path.exists("bdi_agent_log.md"):
        # Create sample log file
        with open("bdi_agent_log.md", 'w') as f:
            f.write("""# BDI Agent Log

## Cycle 1

### Step 1: Read configuration
Result: Success
Beliefs updated: config_path=/path/to/config

### Step 2: Process data
Result: Failed - File not found
Error: Could not locate data.csv

## Cycle 2

### Step 1: Retry with correct path
Result: Success
Beliefs updated: data_loaded=true
""")


def cleanup_log_analysis():
    """Remove log analysis files."""
    if os.path.exists("log_analysis_report.txt"):
        os.remove("log_analysis_report.txt")


def cleanup_import_analysis():
    """Remove import analysis."""
    if os.path.exists("import_analysis.md"):
        os.remove("import_analysis.md")


def cleanup_coverage_report():
    """Remove coverage gap report."""
    if os.path.exists("test_coverage_gaps.md"):
        os.remove("test_coverage_gaps.md")


def cleanup_git_summary():
    """Remove git history summary."""
    if os.path.exists("git_history_summary.md"):
        os.remove("git_history_summary.md")


def cleanup_pipeline_files():
    """Remove data pipeline files."""
    for file in ["sample_data.csv", "transformed_data.json"]:
        if os.path.exists(file):
            os.remove(file)


def cleanup_api_docs():
    """Remove generated API docs."""
    if os.path.exists("api_documentation.md"):
        os.remove("api_documentation.md")


# Complex task cleanup functions

def cleanup_security_audit():
    """Remove security audit report."""
    if os.path.exists("security_audit_report.md"):
        os.remove("security_audit_report.md")


def cleanup_refactoring_plan():
    """Remove refactoring plan."""
    if os.path.exists("refactoring_plan.md"):
        os.remove("refactoring_plan.md")


def cleanup_generated_tests():
    """Remove generated test file."""
    if os.path.exists("test_agent_generated.py"):
        os.remove("test_agent_generated.py")


def cleanup_upgrade_plan():
    """Remove dependency upgrade plan."""
    if os.path.exists("dependency_upgrade_plan.md"):
        os.remove("dependency_upgrade_plan.md")


def cleanup_architecture_docs():
    """Remove architecture documentation."""
    if os.path.exists("architecture_documentation.md"):
        os.remove("architecture_documentation.md")


def cleanup_bug_report():
    """Remove bug report."""
    if os.path.exists("bug_report.md"):
        os.remove("bug_report.md")


def cleanup_performance_plan():
    """Remove performance optimization plan."""
    if os.path.exists("performance_optimization_plan.md"):
        os.remove("performance_optimization_plan.md")


def cleanup_migration_plan():
    """Remove migration plan."""
    if os.path.exists("migration_plan.md"):
        os.remove("migration_plan.md")


# Registry of setup/teardown functions
SETUP_FUNCTIONS = {
    'ensure_readme_exists': ensure_readme_exists,
    'ensure_log_file_exists': ensure_log_file_exists,
}

TEARDOWN_FUNCTIONS = {
    'cleanup_uppercase_file': cleanup_uppercase_file,
    'cleanup_test_directory': cleanup_test_directory,
    'cleanup_report_file': cleanup_report_file,
    'cleanup_dependencies_report': cleanup_dependencies_report,
    'cleanup_log_analysis': cleanup_log_analysis,
    'cleanup_import_analysis': cleanup_import_analysis,
    'cleanup_coverage_report': cleanup_coverage_report,
    'cleanup_git_summary': cleanup_git_summary,
    'cleanup_pipeline_files': cleanup_pipeline_files,
    'cleanup_api_docs': cleanup_api_docs,
    'cleanup_security_audit': cleanup_security_audit,
    'cleanup_refactoring_plan': cleanup_refactoring_plan,
    'cleanup_generated_tests': cleanup_generated_tests,
    'cleanup_upgrade_plan': cleanup_upgrade_plan,
    'cleanup_architecture_docs': cleanup_architecture_docs,
    'cleanup_bug_report': cleanup_bug_report,
    'cleanup_performance_plan': cleanup_performance_plan,
    'cleanup_migration_plan': cleanup_migration_plan,
}


def run_setup(function_name: str):
    """Run a setup function by name."""
    if function_name in SETUP_FUNCTIONS:
        SETUP_FUNCTIONS[function_name]()


def run_teardown(function_name: str):
    """Run a teardown function by name."""
    if function_name in TEARDOWN_FUNCTIONS:
        TEARDOWN_FUNCTIONS[function_name]()
