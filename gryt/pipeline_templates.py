"""
Pipeline template generators for change validation (v1.0.4)
"""
from typing import Optional


def sanitize_change_id(change_id: str) -> str:
    """Convert change ID to valid Python filename/identifier"""
    return change_id.replace("-", "_").replace(" ", "_").upper()


def generate_pipeline_template(
    change_id: str,
    change_type: str,
    title: str,
    description: Optional[str] = None,
) -> str:
    """
    Generate a pipeline template based on change type.

    Args:
        change_id: The change ID (e.g., FEAT-201)
        change_type: Type of change (add, fix, refine, remove)
        title: Change title
        description: Optional change description

    Returns:
        Python code for the validation pipeline
    """
    sanitized_id = sanitize_change_id(change_id)

    # Common imports
    imports = '''"""
Validation pipeline for {change_id}: {title}

Change Type: {change_type}
{description_block}
"""
from gryt import Pipeline, CommandStep, LocalRuntime, SqliteData
from pathlib import Path


'''.format(
        change_id=change_id,
        title=title,
        change_type=change_type,
        description_block=f"Description: {description}" if description else "",
    )

    # Type-specific pipeline logic
    if change_type == "add":
        template = _generate_add_template(sanitized_id, change_id, title)
    elif change_type == "fix":
        template = _generate_fix_template(sanitized_id, change_id, title)
    elif change_type == "refine":
        template = _generate_refine_template(sanitized_id, change_id, title)
    elif change_type == "remove":
        template = _generate_remove_template(sanitized_id, change_id, title)
    else:
        template = _generate_generic_template(sanitized_id, change_id, title)

    return imports + template


def _generate_add_template(sanitized_id: str, change_id: str, title: str) -> str:
    """Generate template for 'add' change type (new feature)"""
    return f'''# Feature validation pipeline for {change_id}
# This pipeline validates the new feature: {title}

def create_pipeline() -> Pipeline:
    """
    Create validation pipeline for new feature.

    Recommended steps:
    - Unit tests for new functionality
    - Integration tests with existing system
    - End-to-end tests for user workflows
    - Security scan for new code
    - Performance benchmarks if applicable
    """

    # Example: Run unit tests for new feature
    unit_test = CommandStep(
        name="unit_tests",
        command="pytest tests/test_{sanitized_id.lower()}.py -v",
        description="Run unit tests for {title}"
    )

    # Example: Run integration tests
    integration_test = CommandStep(
        name="integration_tests",
        command="pytest tests/integration/test_{sanitized_id.lower()}_integration.py -v",
        description="Test integration with existing system"
    )

    # Example: Security scan
    security_scan = CommandStep(
        name="security_scan",
        command="bandit -r src/ -ll",
        description="Security scan for new code"
    )

    pipeline = Pipeline(
        name="{sanitized_id}_VALIDATION",
        steps=[unit_test, integration_test, security_scan],
        parallel_runners=1  # Run sequentially
    )

    return pipeline


if __name__ == "__main__":
    pipeline = create_pipeline()
    runtime = LocalRuntime()
    data = SqliteData(db_path=".gryt/gryt.db")

    result = pipeline.execute(runtime, data)

    if result.get("status") == "pass":
        print(f"✓ Validation passed for {change_id}")
    else:
        print(f"✗ Validation failed for {change_id}")
        exit(1)
'''


def _generate_fix_template(sanitized_id: str, change_id: str, title: str) -> str:
    """Generate template for 'fix' change type (bug fix)"""
    return f'''# Bug fix validation pipeline for {change_id}
# This pipeline validates the bug fix: {title}

def create_pipeline() -> Pipeline:
    """
    Create validation pipeline for bug fix.

    Recommended steps:
    - Regression tests to verify bug is fixed
    - Unit tests for the fixed code
    - Integration tests to ensure no new issues
    - Related feature tests to prevent regressions
    """

    # Example: Run regression test for the bug
    regression_test = CommandStep(
        name="regression_test",
        command="pytest tests/regression/test_{sanitized_id.lower()}_bug.py -v",
        description="Verify bug {change_id} is fixed"
    )

    # Example: Run unit tests for fixed code
    unit_test = CommandStep(
        name="unit_tests",
        command="pytest tests/test_fixed_module.py -v",
        description="Test fixed code functionality"
    )

    # Example: Full test suite to catch regressions
    full_test = CommandStep(
        name="full_test_suite",
        command="pytest tests/ -v --tb=short",
        description="Run full test suite to prevent regressions"
    )

    pipeline = Pipeline(
        name="{sanitized_id}_VALIDATION",
        steps=[regression_test, unit_test, full_test],
        parallel_runners=1
    )

    return pipeline


if __name__ == "__main__":
    pipeline = create_pipeline()
    runtime = LocalRuntime()
    data = SqliteData(db_path=".gryt/gryt.db")

    result = pipeline.execute(runtime, data)

    if result.get("status") == "pass":
        print(f"✓ Bug fix validated for {change_id}")
    else:
        print(f"✗ Validation failed for {change_id}")
        exit(1)
'''


def _generate_refine_template(sanitized_id: str, change_id: str, title: str) -> str:
    """Generate template for 'refine' change type (improvement)"""
    return f'''# Refinement validation pipeline for {change_id}
# This pipeline validates the refinement: {title}

def create_pipeline() -> Pipeline:
    """
    Create validation pipeline for refinement/improvement.

    Recommended steps:
    - Performance benchmarks (before/after comparison)
    - Unit tests for refined code
    - Load tests if applicable
    - UX tests for user-facing improvements
    """

    # Example: Performance benchmark
    benchmark = CommandStep(
        name="benchmark",
        command="pytest tests/benchmarks/test_{sanitized_id.lower()}_perf.py --benchmark-only",
        description="Run performance benchmarks"
    )

    # Example: Unit tests
    unit_test = CommandStep(
        name="unit_tests",
        command="pytest tests/test_refined_module.py -v",
        description="Test refined functionality"
    )

    # Example: Load test
    load_test = CommandStep(
        name="load_test",
        command="locust -f tests/load/test_{sanitized_id.lower()}_load.py --headless -u 100 -r 10 -t 1m",
        description="Run load tests"
    )

    pipeline = Pipeline(
        name="{sanitized_id}_VALIDATION",
        steps=[unit_test, benchmark, load_test],
        parallel_runners=1
    )

    return pipeline


if __name__ == "__main__":
    pipeline = create_pipeline()
    runtime = LocalRuntime()
    data = SqliteData(db_path=".gryt/gryt.db")

    result = pipeline.execute(runtime, data)

    if result.get("status") == "pass":
        print(f"✓ Refinement validated for {change_id}")
    else:
        print(f"✗ Validation failed for {change_id}")
        exit(1)
'''


def _generate_remove_template(sanitized_id: str, change_id: str, title: str) -> str:
    """Generate template for 'remove' change type (deprecation/removal)"""
    return f'''# Removal validation pipeline for {change_id}
# This pipeline validates the removal/deprecation: {title}

def create_pipeline() -> Pipeline:
    """
    Create validation pipeline for removal/deprecation.

    Recommended steps:
    - Verify removed code is no longer referenced
    - Test migration paths for affected users
    - Ensure replacement functionality works
    - Check documentation updates
    """

    # Example: Check for orphaned references
    check_references = CommandStep(
        name="check_references",
        command="grep -r '{sanitized_id.lower()}' src/ || true",
        description="Check for orphaned references"
    )

    # Example: Test replacement functionality
    replacement_test = CommandStep(
        name="replacement_test",
        command="pytest tests/test_replacement_functionality.py -v",
        description="Test replacement functionality"
    )

    # Example: Full test suite
    full_test = CommandStep(
        name="full_test_suite",
        command="pytest tests/ -v",
        description="Verify no broken dependencies"
    )

    pipeline = Pipeline(
        name="{sanitized_id}_VALIDATION",
        steps=[check_references, replacement_test, full_test],
        parallel_runners=1
    )

    return pipeline


if __name__ == "__main__":
    pipeline = create_pipeline()
    runtime = LocalRuntime()
    data = SqliteData(db_path=".gryt/gryt.db")

    result = pipeline.execute(runtime, data)

    if result.get("status") == "pass":
        print(f"✓ Removal validated for {change_id}")
    else:
        print(f"✗ Validation failed for {change_id}")
        exit(1)
'''


def _generate_generic_template(sanitized_id: str, change_id: str, title: str) -> str:
    """Generate generic template for unknown change types"""
    return f'''# Validation pipeline for {change_id}
# This pipeline validates: {title}

def create_pipeline() -> Pipeline:
    """
    Create validation pipeline.

    TODO: Customize this pipeline based on your specific needs.
    """

    # Example: Run tests
    test_step = CommandStep(
        name="tests",
        command="pytest tests/ -v",
        description="Run tests"
    )

    # Example: Run linting
    lint_step = CommandStep(
        name="lint",
        command="pylint src/",
        description="Run code quality checks"
    )

    pipeline = Pipeline(
        name="{sanitized_id}_VALIDATION",
        steps=[test_step, lint_step],
        parallel_runners=1
    )

    return pipeline


if __name__ == "__main__":
    pipeline = create_pipeline()
    runtime = LocalRuntime()
    data = SqliteData(db_path=".gryt/gryt.db")

    result = pipeline.execute(runtime, data)

    if result.get("status") == "pass":
        print(f"✓ Validation passed for {change_id}")
    else:
        print(f"✗ Validation failed for {change_id}")
        exit(1)
'''
