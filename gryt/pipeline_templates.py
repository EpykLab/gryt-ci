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

    # Common header
    header = '''#!/usr/bin/env python3
"""
Validation pipeline for {change_id}: {title}

Change Type: {change_type}
{description_block}
"""
from gryt import LocalRuntime, Pipeline, Runner, SqliteData, CommandStep

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

    return header + template


def _generate_add_template(sanitized_id: str, change_id: str, title: str) -> str:
    """Generate template for 'add' change type (new feature)"""
    return f'''# Feature validation pipeline for {change_id}
# This pipeline validates the new feature: {title}
#
# Recommended steps:
# - Unit tests for new functionality
# - Integration tests with existing system
# - End-to-end tests for user workflows
# - Security scan for new code
# - Performance benchmarks if applicable

data = SqliteData(db_path='.gryt/gryt.db')
runtime = LocalRuntime()

# TODO: Customize these steps for your specific validation needs
runner = Runner([
    CommandStep(
        id="unit_tests",
        config={{
            'cmd': ['pytest', 'tests/test_{sanitized_id.lower()}.py', '-v'],
            'cwd': '.',
        }},
        data=data
    ),
    CommandStep(
        id="integration_tests",
        config={{
            'cmd': ['pytest', 'tests/integration/test_{sanitized_id.lower()}_integration.py', '-v'],
            'cwd': '.',
        }},
        data=data
    ),
    CommandStep(
        id="security_scan",
        config={{
            'cmd': ['bandit', '-r', 'src/', '-ll'],
            'cwd': '.',
        }},
        data=data
    ),
], data=data)

PIPELINE = Pipeline([runner], data=data, runtime=runtime)
'''


def _generate_fix_template(sanitized_id: str, change_id: str, title: str) -> str:
    """Generate template for 'fix' change type (bug fix)"""
    return f'''# Bug fix validation pipeline for {change_id}
# This pipeline validates the bug fix: {title}
#
# Recommended steps:
# - Regression tests to verify bug is fixed
# - Unit tests for the fixed code
# - Integration tests to ensure no new issues
# - Related feature tests to prevent regressions

data = SqliteData(db_path='.gryt/gryt.db')
runtime = LocalRuntime()

# TODO: Customize these steps for your specific validation needs
runner = Runner([
    CommandStep(
        id="regression_test",
        config={{
            'cmd': ['pytest', 'tests/regression/test_{sanitized_id.lower()}_bug.py', '-v'],
            'cwd': '.',
        }},
        data=data
    ),
    CommandStep(
        id="unit_tests",
        config={{
            'cmd': ['pytest', 'tests/test_fixed_module.py', '-v'],
            'cwd': '.',
        }},
        data=data
    ),
    CommandStep(
        id="full_test_suite",
        config={{
            'cmd': ['pytest', 'tests/', '-v', '--tb=short'],
            'cwd': '.',
        }},
        data=data
    ),
], data=data)

PIPELINE = Pipeline([runner], data=data, runtime=runtime)
'''


def _generate_refine_template(sanitized_id: str, change_id: str, title: str) -> str:
    """Generate template for 'refine' change type (improvement)"""
    return f'''# Refinement validation pipeline for {change_id}
# This pipeline validates the refinement: {title}
#
# Recommended steps:
# - Performance benchmarks (before/after comparison)
# - Unit tests for refined code
# - Load tests if applicable
# - UX tests for user-facing improvements

data = SqliteData(db_path='.gryt/gryt.db')
runtime = LocalRuntime()

# TODO: Customize these steps for your specific validation needs
runner = Runner([
    CommandStep(
        id="unit_tests",
        config={{
            'cmd': ['pytest', 'tests/test_refined_module.py', '-v'],
            'cwd': '.',
        }},
        data=data
    ),
    CommandStep(
        id="benchmark",
        config={{
            'cmd': ['pytest', 'tests/benchmarks/test_{sanitized_id.lower()}_perf.py', '--benchmark-only'],
            'cwd': '.',
        }},
        data=data
    ),
    CommandStep(
        id="load_test",
        config={{
            'cmd': ['locust', '-f', 'tests/load/test_{sanitized_id.lower()}_load.py', '--headless', '-u', '100', '-r', '10', '-t', '1m'],
            'cwd': '.',
        }},
        data=data
    ),
], data=data)

PIPELINE = Pipeline([runner], data=data, runtime=runtime)
'''


def _generate_remove_template(sanitized_id: str, change_id: str, title: str) -> str:
    """Generate template for 'remove' change type (deprecation/removal)"""
    return f'''# Removal validation pipeline for {change_id}
# This pipeline validates the removal/deprecation: {title}
#
# Recommended steps:
# - Verify removed code is no longer referenced
# - Test migration paths for affected users
# - Ensure replacement functionality works
# - Check documentation updates

data = SqliteData(db_path='.gryt/gryt.db')
runtime = LocalRuntime()

# TODO: Customize these steps for your specific validation needs
runner = Runner([
    CommandStep(
        id="check_references",
        config={{
            'cmd': ['grep', '-r', '{sanitized_id.lower()}', 'src/'],
            'cwd': '.',
        }},
        data=data
    ),
    CommandStep(
        id="replacement_test",
        config={{
            'cmd': ['pytest', 'tests/test_replacement_functionality.py', '-v'],
            'cwd': '.',
        }},
        data=data
    ),
    CommandStep(
        id="full_test_suite",
        config={{
            'cmd': ['pytest', 'tests/', '-v'],
            'cwd': '.',
        }},
        data=data
    ),
], data=data)

PIPELINE = Pipeline([runner], data=data, runtime=runtime)
'''


def _generate_generic_template(sanitized_id: str, change_id: str, title: str) -> str:
    """Generate generic template for unknown change types"""
    return f'''# Validation pipeline for {change_id}
# This pipeline validates: {title}
#
# TODO: Customize this pipeline based on your specific needs

data = SqliteData(db_path='.gryt/gryt.db')
runtime = LocalRuntime()

runner = Runner([
    CommandStep(
        id="tests",
        config={{
            'cmd': ['pytest', 'tests/', '-v'],
            'cwd': '.',
        }},
        data=data
    ),
    CommandStep(
        id="lint",
        config={{
            'cmd': ['pylint', 'src/'],
            'cwd': '.',
        }},
        data=data
    ),
], data=data)

PIPELINE = Pipeline([runner], data=data, runtime=runtime)
'''
