# gryt-ci Test Suite

## Overview

Comprehensive test suite for gryt-ci covering all major functionality from core primitives through v1.0.0 features.

## Test Statistics

- **Total Tests**: 66
- **Passing**: 66 (100%)
- **Test Files**: 6
- **Test Classes**: 21

## Running Tests

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/test_generation.py

# Run specific test class
pytest tests/test_gates.py::TestAllChangesProvenGate

# Run with coverage report
pytest tests/ --cov=gryt --cov-report=html
```

## Test Coverage by Module

### Core Functionality (`test_data.py`)
**6 tests** covering `gryt.data.SqliteData`:
- ✅ Database initialization with required tables
- ✅ Insert and query operations
- ✅ Update operations
- ✅ Foreign key cascade deletion
- ✅ JSON serialization/deserialization
- ✅ Thread-safe concurrent access

### Generation & Evolution (`test_generation.py`)
**8 tests** covering v0.2.0 and v0.3.0 features:
- ✅ Creating generations with changes
- ✅ Loading generations from database
- ✅ Generation promotion workflow
- ✅ Promotion failure with unproven changes
- ✅ Creating evolutions
- ✅ Auto-increment RC tag generation (v1.0.0-rc.1 → rc.2 → rc.3)
- ✅ Listing evolutions for a generation
- ✅ Updating evolution status

### Promotion Gates (`test_gates.py`)
**8 tests** covering v0.4.0 features:
- ✅ AllChangesProvenGate success and failure scenarios
- ✅ NoFailedEvolutionsGate validation
- ✅ MinEvolutionsGate with configurable minimums
- ✅ Default gate configuration
- ✅ Multi-gate integration testing

### Policy & Hooks (`test_policy.py`)
**13 tests** covering v0.5.0 features:
- ✅ Policy creation and configuration
- ✅ Policy applies_to logic for change types
- ✅ Change type validation (success/failure)
- ✅ Policy serialization (to_dict/from_dict)
- ✅ PolicySet loading from YAML files
- ✅ Multi-policy validation
- ✅ PolicyHook validation for evolutions
- ✅ ChangeTypeHook callbacks (add/fix/refine/remove)
- ✅ Exception handling in callbacks

### Templates (`test_templates.py`)
**14 tests** covering v0.6.0 features:
- ✅ Template creation and configuration
- ✅ Template rendering with directory structure
- ✅ Variable substitution ({{project_name}})
- ✅ Pipeline template rendering
- ✅ Generation example rendering
- ✅ Template registry management
- ✅ Built-in template creation (Go, Python, Node, Minimal)
- ✅ Template rendering integration tests
- ✅ Global registry singleton pattern

### Audit, Rollback & Compliance (`test_audit.py`)
**17 tests** covering v1.0.0 features:
- ✅ **Audit Trail** (4 tests):
  - Event logging with full metadata
  - JSON export with complete audit data
  - CSV export for spreadsheet analysis
  - HTML export for human-readable reports
- ✅ **Rollback Manager** (3 tests):
  - Database snapshot creation with labels
  - Snapshot listing with metadata
  - Rollback to previous state with backup
- ✅ **Hot-fix Workflow** (5 tests):
  - HotfixGate validation (passes with one evolution)
  - HotfixGate failure detection (pending evolutions)
  - Version calculation (v1.2.0 → v1.2.1)
  - Version auto-increment (v1.2.1 → v1.2.2)
  - create_hotfix helper function
- ✅ **Compliance Report** (3 tests):
  - NIST 800-161 report generation
  - Statistics inclusion and accuracy
  - generate_compliance_report helper
- ✅ **Integration Tests** (2 tests):
  - Complete hot-fix workflow (create → evolve → promote)
  - Audit trail captures full workflow

## Test Fixtures

### `temp_dir`
Provides a temporary directory for test files that is automatically cleaned up.

### `test_db`
Provides a fresh SqliteData instance with all tables initialized for each test.

### `test_db_path`
Provides a Path to a test database (for functions that require a Path argument instead of SqliteData instance).

### `gryt_project`
Provides a complete temporary gryt project structure with `.gryt` directory, database, and subdirectories.

## Test Organization

Tests are organized by feature/module:
```
tests/
├── __init__.py
├── conftest.py           # Shared fixtures
├── test_data.py          # Core data layer
├── test_generation.py    # Generation/Evolution (v0.2.0, v0.3.0)
├── test_gates.py         # Promotion Gates (v0.4.0)
├── test_policy.py        # Policy & Hooks (v0.5.0)
├── test_templates.py     # Templates (v0.6.0)
└── test_audit.py         # Audit, Rollback & Compliance (v1.0.0)
```

## Key Testing Patterns

### Database Testing
All database tests use isolated temporary databases via the `test_db` fixture, ensuring no cross-test contamination.

### Integration Testing
Multi-component tests verify that features work together correctly (e.g., promotion gates with generations and evolutions).

### Error Path Testing
Tests cover both success and failure scenarios, including:
- Policy violations
- Gate failures
- Missing data validation
- Exception handling

## Continuous Integration

Tests are designed to run quickly (<1 second total) and can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Tests
  run: |
    pip install -r requirements-test.txt
    pytest tests/ -v
```

## Coverage Goals

Current coverage focuses on:
- ✅ Core functionality (Data, Pipeline primitives)
- ✅ Generation/Evolution workflow (v0.2.0, v0.3.0)
- ✅ Promotion Gates (v0.4.0)
- ✅ Policy enforcement and hooks (v0.5.0)
- ✅ Template system (v0.6.0)
- ✅ Audit trail, rollback, hot-fix, and compliance (v1.0.0)

## Adding New Tests

When adding new features:
1. Create tests in the appropriate test file (or new file for new modules)
2. Use existing fixtures when possible
3. Follow the Test<ComponentName> class naming convention
4. Add docstrings describing what each test validates
5. Test both success and failure paths
6. Run full test suite to ensure no regressions

## Test Best Practices

- ✅ **Isolation**: Each test is independent and can run in any order
- ✅ **Fast**: All tests complete in under 1 second
- ✅ **Clear**: Test names describe what they verify
- ✅ **Comprehensive**: Cover success, failure, and edge cases
- ✅ **Maintainable**: Use fixtures to reduce duplication

## Future Testing

Areas for expanded coverage:
- [ ] Dashboard rendering and updates
- [ ] Cloud sync integration
- [ ] CLI command execution
- [ ] Destination publishing (Slack, Prometheus)
- [ ] End-to-end workflow tests
- [ ] Performance/load testing
