"""Validation functions for task success criteria."""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


class ValidationResult:
    """Result of a validation check."""

    def __init__(self, success: bool, message: str = "", details: Optional[Dict[str, Any]] = None):
        self.success = success
        self.message = message
        self.details = details or {}


def file_exists(file_path: str, **kwargs) -> ValidationResult:
    """Check if a file exists."""
    exists = os.path.exists(file_path)
    return ValidationResult(
        success=exists,
        message=f"File {'exists' if exists else 'does not exist'}: {file_path}",
        details={"file_path": file_path, "exists": exists}
    )


def directory_exists(path: str, **kwargs) -> ValidationResult:
    """Check if a directory exists."""
    exists = os.path.isdir(path)
    return ValidationResult(
        success=exists,
        message=f"Directory {'exists' if exists else 'does not exist'}: {path}",
        details={"path": path, "exists": exists}
    )


def file_was_read(file_path: str, execution_log: str = "", **kwargs) -> ValidationResult:
    """Check if a file was successfully read during execution."""
    # Check both file existence and log evidence
    exists = os.path.exists(file_path)
    mentioned_in_log = file_path in execution_log if execution_log else False

    success = exists and (mentioned_in_log or not execution_log)
    return ValidationResult(
        success=success,
        message=f"File read: {file_path}",
        details={"file_path": file_path, "exists": exists, "mentioned": mentioned_in_log}
    )


def correct_line_count(file_path: str, tolerance: int = 0, **kwargs) -> ValidationResult:
    """Verify correct line count was reported."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            actual_lines = len(f.readlines())

        # This would need to be compared against agent's reported count
        # For now, just verify we can count
        return ValidationResult(
            success=True,
            message=f"Line count determined: {actual_lines}",
            details={"file_path": file_path, "line_count": actual_lines}
        )
    except Exception as e:
        return ValidationResult(success=False, message=f"Error counting lines: {e}")


def all_python_files_found(directory: str, final_state: Dict[str, Any] = None, **kwargs) -> ValidationResult:
    """Check if all Python files in directory were found."""
    try:
        actual_files = set()
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith('.py'):
                    actual_files.add(os.path.join(root, file))

        # Check if agent reported similar count
        reported_files = final_state.get('python_files', []) if final_state else []

        success = len(reported_files) >= len(actual_files) * 0.9  # 90% threshold
        return ValidationResult(
            success=success,
            message=f"Found {len(reported_files)} of {len(actual_files)} Python files",
            details={"actual_count": len(actual_files), "reported_count": len(reported_files)}
        )
    except Exception as e:
        return ValidationResult(success=False, message=f"Error finding files: {e}")


def no_false_positives(extension: str, final_state: Dict[str, Any] = None, **kwargs) -> ValidationResult:
    """Check that only files with correct extension were reported."""
    reported_files = final_state.get('python_files', []) if final_state else []

    false_positives = [f for f in reported_files if not f.endswith(extension)]

    success = len(false_positives) == 0
    return ValidationResult(
        success=success,
        message=f"No false positives found" if success else f"Found {len(false_positives)} false positives",
        details={"false_positives": false_positives}
    )


def json_parsed_successfully(execution_log: str = "", **kwargs) -> ValidationResult:
    """Check if JSON was parsed successfully."""
    # Look for evidence in log
    success_indicators = ['parsed', 'json', 'loaded']
    success = any(indicator in execution_log.lower() for indicator in success_indicators)

    return ValidationResult(
        success=success,
        message="JSON parsing attempted",
        details={}
    )


def field_extracted(field_name: str, final_state: Dict[str, Any] = None, **kwargs) -> ValidationResult:
    """Check if a specific field was extracted."""
    if final_state and field_name in final_state:
        return ValidationResult(
            success=True,
            message=f"Field '{field_name}' extracted: {final_state[field_name]}",
            details={"field_name": field_name, "value": final_state[field_name]}
        )

    return ValidationResult(
        success=False,
        message=f"Field '{field_name}' not found in final state",
        details={"field_name": field_name}
    )


def text_is_uppercase(file_path: str, **kwargs) -> ValidationResult:
    """Check if text file contains uppercase text."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check if at least 80% of alphabetic characters are uppercase
        alpha_chars = [c for c in content if c.isalpha()]
        if not alpha_chars:
            return ValidationResult(success=False, message="No alphabetic characters found")

        uppercase_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
        success = uppercase_ratio >= 0.8

        return ValidationResult(
            success=success,
            message=f"Uppercase ratio: {uppercase_ratio:.2%}",
            details={"uppercase_ratio": uppercase_ratio}
        )
    except Exception as e:
        return ValidationResult(success=False, message=f"Error reading file: {e}")


def function_count_accurate(file_path: str, tolerance: int = 1, final_state: Dict[str, Any] = None, **kwargs) -> ValidationResult:
    """Check if function count is accurate."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Count actual function definitions
        actual_count = len(re.findall(r'^\s*def\s+\w+', content, re.MULTILINE))

        reported_count = final_state.get('function_count', 0) if final_state else 0

        difference = abs(actual_count - reported_count)
        success = difference <= tolerance

        return ValidationResult(
            success=success,
            message=f"Function count: actual={actual_count}, reported={reported_count}",
            details={"actual": actual_count, "reported": reported_count, "difference": difference}
        )
    except Exception as e:
        return ValidationResult(success=False, message=f"Error counting functions: {e}")


def subdirectories_exist(base: str, subdirs: List[str], **kwargs) -> ValidationResult:
    """Check if subdirectories exist."""
    missing = []
    for subdir in subdirs:
        path = os.path.join(base, subdir)
        if not os.path.isdir(path):
            missing.append(subdir)

    success = len(missing) == 0
    return ValidationResult(
        success=success,
        message=f"All subdirectories exist" if success else f"Missing: {missing}",
        details={"missing": missing, "expected": subdirs}
    )


def word_count_accurate(file_path: str, tolerance_percent: float = 5.0, final_state: Dict[str, Any] = None, **kwargs) -> ValidationResult:
    """Check if word count is accurate within tolerance."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        actual_count = len(content.split())
        reported_count = final_state.get('word_count', 0) if final_state else 0

        if actual_count == 0:
            return ValidationResult(success=False, message="File is empty")

        difference_percent = abs(actual_count - reported_count) / actual_count * 100
        success = difference_percent <= tolerance_percent

        return ValidationResult(
            success=success,
            message=f"Word count: actual={actual_count}, reported={reported_count}, diff={difference_percent:.1f}%",
            details={"actual": actual_count, "reported": reported_count, "difference_percent": difference_percent}
        )
    except Exception as e:
        return ValidationResult(success=False, message=f"Error counting words: {e}")


def valid_json_file(file_path: str, **kwargs) -> ValidationResult:
    """Check if file contains valid JSON."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            json.load(f)
        return ValidationResult(success=True, message=f"Valid JSON file: {file_path}")
    except json.JSONDecodeError as e:
        return ValidationResult(success=False, message=f"Invalid JSON: {e}")
    except Exception as e:
        return ValidationResult(success=False, message=f"Error reading file: {e}")


def branch_identified(final_state: Dict[str, Any] = None, **kwargs) -> ValidationResult:
    """Check if git branch was identified."""
    branch = final_state.get('git_branch') if final_state else None
    success = branch is not None and len(str(branch)) > 0

    return ValidationResult(
        success=success,
        message=f"Branch identified: {branch}" if success else "Branch not identified",
        details={"branch": branch}
    )


def status_determined(final_state: Dict[str, Any] = None, **kwargs) -> ValidationResult:
    """Check if git status was determined."""
    status = final_state.get('git_status') if final_state else None
    success = status is not None

    return ValidationResult(
        success=success,
        message=f"Status determined: {status}" if success else "Status not determined",
        details={"status": status}
    )


# Medium task validators

def all_files_analyzed(directory: str, final_state: Dict[str, Any] = None, **kwargs) -> ValidationResult:
    """Check if all files were analyzed."""
    analyzed_count = final_state.get('files_analyzed', 0) if final_state else 0
    success = analyzed_count > 0

    return ValidationResult(
        success=success,
        message=f"Files analyzed: {analyzed_count}",
        details={"analyzed_count": analyzed_count}
    )


def report_contains_counts(required_fields: List[str], file_path: str, **kwargs) -> ValidationResult:
    """Check if report contains required count fields."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().lower()

        found_fields = [field for field in required_fields if field in content]
        success = len(found_fields) == len(required_fields)

        return ValidationResult(
            success=success,
            message=f"Found {len(found_fields)}/{len(required_fields)} required fields",
            details={"found": found_fields, "required": required_fields}
        )
    except Exception as e:
        return ValidationResult(success=False, message=f"Error reading report: {e}")


def toml_parsed(file_path: str, **kwargs) -> ValidationResult:
    """Check if TOML file was parsed."""
    # Try to import toml library and parse
    try:
        import tomli
        with open(file_path, 'rb') as f:
            tomli.load(f)
        return ValidationResult(success=True, message="TOML parsed successfully")
    except ImportError:
        # Fallback: check if file exists and has content
        return file_exists(file_path)
    except Exception as e:
        return ValidationResult(success=False, message=f"Error parsing TOML: {e}")


def dependencies_extracted(min_dependencies: int, final_state: Dict[str, Any] = None, **kwargs) -> ValidationResult:
    """Check if dependencies were extracted."""
    deps = final_state.get('dependencies', []) if final_state else []
    count = len(deps) if isinstance(deps, list) else (deps if isinstance(deps, int) else 0)

    success = count >= min_dependencies

    return ValidationResult(
        success=success,
        message=f"Dependencies extracted: {count}",
        details={"count": count, "min_required": min_dependencies}
    )


def patterns_identified(final_state: Dict[str, Any] = None, **kwargs) -> ValidationResult:
    """Check if patterns were identified."""
    patterns = final_state.get('patterns', []) if final_state else []
    success = len(patterns) > 0

    return ValidationResult(
        success=success,
        message=f"Patterns identified: {len(patterns)}",
        details={"pattern_count": len(patterns)}
    )


def imports_identified(final_state: Dict[str, Any] = None, **kwargs) -> ValidationResult:
    """Check if imports were identified."""
    imports = final_state.get('imports', []) if final_state else []
    success = len(imports) > 0

    return ValidationResult(
        success=success,
        message=f"Imports identified: {len(imports)}",
        details={"import_count": len(imports)}
    )


def directory_scanned(directory: str, final_state: Dict[str, Any] = None, **kwargs) -> ValidationResult:
    """Check if directory was scanned."""
    scanned_dirs = final_state.get('scanned_directories', []) if final_state else []
    success = directory in scanned_dirs or len(scanned_dirs) > 0

    return ValidationResult(
        success=success,
        message=f"Directory scanned: {directory}",
        details={"scanned": scanned_dirs}
    )


def gaps_identified(final_state: Dict[str, Any] = None, **kwargs) -> ValidationResult:
    """Check if coverage gaps were identified."""
    gaps = final_state.get('coverage_gaps', []) if final_state else []
    # Success means we checked (gaps found or explicitly none found)
    success = isinstance(gaps, list)

    return ValidationResult(
        success=success,
        message=f"Coverage gaps: {len(gaps)}",
        details={"gap_count": len(gaps)}
    )


def git_log_retrieved(min_commits: int, final_state: Dict[str, Any] = None, **kwargs) -> ValidationResult:
    """Check if git log was retrieved."""
    commits = final_state.get('commits', []) if final_state else []
    commit_count = len(commits) if isinstance(commits, list) else (commits if isinstance(commits, int) else 0)

    success = commit_count >= min_commits

    return ValidationResult(
        success=success,
        message=f"Commits retrieved: {commit_count}",
        details={"count": commit_count, "min_required": min_commits}
    )


def commits_categorized(final_state: Dict[str, Any] = None, **kwargs) -> ValidationResult:
    """Check if commits were categorized."""
    categories = final_state.get('commit_categories', {}) if final_state else {}
    success = len(categories) > 0

    return ValidationResult(
        success=success,
        message=f"Commit categories: {len(categories)}",
        details={"categories": list(categories.keys())}
    )


def data_transformed(final_state: Dict[str, Any] = None, **kwargs) -> ValidationResult:
    """Check if data was transformed."""
    transformed = final_state.get('data_transformed', False) if final_state else False
    return ValidationResult(
        success=bool(transformed),
        message="Data transformation completed" if transformed else "Data not transformed"
    )


def docstrings_extracted(min_docstrings: int, final_state: Dict[str, Any] = None, **kwargs) -> ValidationResult:
    """Check if docstrings were extracted."""
    docstrings = final_state.get('docstrings', []) if final_state else []
    count = len(docstrings) if isinstance(docstrings, list) else 0

    success = count >= min_docstrings

    return ValidationResult(
        success=success,
        message=f"Docstrings extracted: {count}",
        details={"count": count, "min_required": min_docstrings}
    )


# Complex task validators (stubs - can be enhanced)

def all_directories_scanned(directories: List[str], final_state: Dict[str, Any] = None, **kwargs) -> ValidationResult:
    """Check if all directories were scanned."""
    scanned = final_state.get('scanned_directories', []) if final_state else []
    missing = [d for d in directories if d not in scanned]

    success = len(missing) == 0 or len(scanned) >= len(directories)

    return ValidationResult(
        success=success,
        message=f"Directories scanned: {len(scanned)}/{len(directories)}",
        details={"scanned": scanned, "missing": missing}
    )


def security_patterns_checked(patterns: List[str], final_state: Dict[str, Any] = None, **kwargs) -> ValidationResult:
    """Check if security patterns were checked."""
    checked_patterns = final_state.get('security_patterns_checked', []) if final_state else []
    success = len(checked_patterns) >= len(patterns) * 0.75  # 75% threshold

    return ValidationResult(
        success=success,
        message=f"Security patterns checked: {len(checked_patterns)}",
        details={"checked": len(checked_patterns), "total_patterns": len(patterns)}
    )


def comprehensive_report(file_path: str, min_sections: int, **kwargs) -> ValidationResult:
    """Check if comprehensive report was created."""
    if not os.path.exists(file_path):
        return ValidationResult(success=False, message=f"Report file not found: {file_path}")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Count markdown headers as sections
        section_count = len(re.findall(r'^#+\s', content, re.MULTILINE))
        success = section_count >= min_sections

        return ValidationResult(
            success=success,
            message=f"Report sections: {section_count}",
            details={"sections": section_count, "min_required": min_sections}
        )
    except Exception as e:
        return ValidationResult(success=False, message=f"Error reading report: {e}")


def quality_issues_found(min_issues: int, final_state: Dict[str, Any] = None, **kwargs) -> ValidationResult:
    """Check if quality issues were found."""
    issues = final_state.get('quality_issues', []) if final_state else []
    count = len(issues) if isinstance(issues, list) else 0

    success = count >= min_issues

    return ValidationResult(
        success=success,
        message=f"Quality issues found: {count}",
        details={"count": count, "min_required": min_issues}
    )


def duplication_analyzed(final_state: Dict[str, Any] = None, **kwargs) -> ValidationResult:
    """Check if code duplication was analyzed."""
    analyzed = final_state.get('duplication_analyzed', False) if final_state else False
    return ValidationResult(
        success=bool(analyzed),
        message="Duplication analysis completed" if analyzed else "Duplication not analyzed"
    )


def prioritized_plan_created(file_path: str, **kwargs) -> ValidationResult:
    """Check if prioritized plan was created."""
    if not os.path.exists(file_path):
        return ValidationResult(success=False, message=f"Plan file not found: {file_path}")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Look for priority indicators
        has_priority = any(word in content.lower() for word in ['priority', 'critical', 'high', 'medium', 'low'])
        success = has_priority and len(content) > 100

        return ValidationResult(
            success=success,
            message="Prioritized plan created" if success else "Plan lacks prioritization",
            details={"has_priority": has_priority, "content_length": len(content)}
        )
    except Exception as e:
        return ValidationResult(success=False, message=f"Error reading plan: {e}")


def valid_python_file(file_path: str, **kwargs) -> ValidationResult:
    """Check if file is valid Python."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        import ast
        ast.parse(content)
        return ValidationResult(success=True, message=f"Valid Python file: {file_path}")
    except SyntaxError as e:
        return ValidationResult(success=False, message=f"Python syntax error: {e}")
    except Exception as e:
        return ValidationResult(success=False, message=f"Error validating Python: {e}")


def multiple_test_cases(file_path: str, min_tests: int, **kwargs) -> ValidationResult:
    """Check if multiple test cases exist."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        test_count = len(re.findall(r'^\s*def\s+test_\w+', content, re.MULTILINE))
        success = test_count >= min_tests

        return ValidationResult(
            success=success,
            message=f"Test cases found: {test_count}",
            details={"test_count": test_count, "min_required": min_tests}
        )
    except Exception as e:
        return ValidationResult(success=False, message=f"Error analyzing tests: {e}")


def edge_cases_covered(final_state: Dict[str, Any] = None, **kwargs) -> ValidationResult:
    """Check if edge cases were covered."""
    edge_cases = final_state.get('edge_cases', []) if final_state else []
    success = len(edge_cases) > 0

    return ValidationResult(
        success=success,
        message=f"Edge cases covered: {len(edge_cases)}",
        details={"edge_case_count": len(edge_cases)}
    )


# Additional validators for complex tasks (stubs)
dependencies_analyzed = lambda **kwargs: ValidationResult(True, "Dependencies analyzed")
impact_assessed = lambda **kwargs: ValidationResult(True, "Impact assessed")
phased_plan_created = lambda file_path, min_phases, **kwargs: file_exists(file_path, **kwargs)
components_identified = lambda min_components, **kwargs: ValidationResult(True, f"Components identified: {min_components}")
dependencies_mapped = lambda **kwargs: ValidationResult(True, "Dependencies mapped")
architecture_doc_with_diagrams = lambda file_path, **kwargs: file_exists(file_path, **kwargs)
all_files_scanned = lambda directories, **kwargs: ValidationResult(True, f"Files scanned in {len(directories)} directories")
bug_categories_checked = lambda min_categories, **kwargs: ValidationResult(True, f"Bug categories checked: {min_categories}")
prioritized_bug_report = lambda file_path, **kwargs: file_exists(file_path, **kwargs)
hotspots_identified = lambda min_hotspots, **kwargs: ValidationResult(True, f"Hotspots identified: {min_hotspots}")
complexity_analyzed = lambda **kwargs: ValidationResult(True, "Complexity analyzed")
optimization_roadmap = lambda file_path, **kwargs: file_exists(file_path, **kwargs)
framework_usage_analyzed = lambda directory, **kwargs: ValidationResult(True, f"Framework usage analyzed in {directory}")
breaking_changes_identified = lambda **kwargs: ValidationResult(True, "Breaking changes identified")
migration_plan_created = lambda file_path, min_phases, **kwargs: file_exists(file_path, **kwargs)


# Registry of all validators
VALIDATORS = {
    'file_exists': file_exists,
    'directory_exists': directory_exists,
    'file_was_read': file_was_read,
    'correct_line_count': correct_line_count,
    'all_python_files_found': all_python_files_found,
    'no_false_positives': no_false_positives,
    'json_parsed_successfully': json_parsed_successfully,
    'field_extracted': field_extracted,
    'text_is_uppercase': text_is_uppercase,
    'function_count_accurate': function_count_accurate,
    'subdirectories_exist': subdirectories_exist,
    'word_count_accurate': word_count_accurate,
    'valid_json_file': valid_json_file,
    'branch_identified': branch_identified,
    'status_determined': status_determined,
    'all_files_analyzed': all_files_analyzed,
    'report_contains_counts': report_contains_counts,
    'toml_parsed': toml_parsed,
    'dependencies_extracted': dependencies_extracted,
    'patterns_identified': patterns_identified,
    'imports_identified': imports_identified,
    'directory_scanned': directory_scanned,
    'gaps_identified': gaps_identified,
    'git_log_retrieved': git_log_retrieved,
    'commits_categorized': commits_categorized,
    'data_transformed': data_transformed,
    'docstrings_extracted': docstrings_extracted,
    'all_directories_scanned': all_directories_scanned,
    'security_patterns_checked': security_patterns_checked,
    'comprehensive_report': comprehensive_report,
    'quality_issues_found': quality_issues_found,
    'duplication_analyzed': duplication_analyzed,
    'prioritized_plan_created': prioritized_plan_created,
    'valid_python_file': valid_python_file,
    'multiple_test_cases': multiple_test_cases,
    'edge_cases_covered': edge_cases_covered,
    'dependencies_analyzed': dependencies_analyzed,
    'impact_assessed': impact_assessed,
    'phased_plan_created': phased_plan_created,
    'components_identified': components_identified,
    'dependencies_mapped': dependencies_mapped,
    'architecture_doc_with_diagrams': architecture_doc_with_diagrams,
    'all_files_scanned': all_files_scanned,
    'bug_categories_checked': bug_categories_checked,
    'prioritized_bug_report': prioritized_bug_report,
    'hotspots_identified': hotspots_identified,
    'complexity_analyzed': complexity_analyzed,
    'optimization_roadmap': optimization_roadmap,
    'framework_usage_analyzed': framework_usage_analyzed,
    'breaking_changes_identified': breaking_changes_identified,
    'migration_plan_created': migration_plan_created,
}


def run_validator(validator_name: str, **kwargs) -> ValidationResult:
    """Run a validator by name."""
    validator_func = VALIDATORS.get(validator_name)

    if validator_func is None:
        return ValidationResult(
            success=False,
            message=f"Unknown validator: {validator_name}"
        )

    try:
        return validator_func(**kwargs)
    except Exception as e:
        return ValidationResult(
            success=False,
            message=f"Validator error: {e}",
            details={"error": str(e), "validator": validator_name}
        )
