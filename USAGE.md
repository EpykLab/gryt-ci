# gryt-ci Usage Guide

## Quick Start

```bash
# Initialize project
gryt init

# Create release contract
gryt generation new v1.0.0

# Edit generation file
vim .gryt/generations/v1.0.0.yaml

# Start evolution (prove a change)
gryt evolution start v1.0.0 --change FEAT-001

# Run your pipeline
gryt run my-pipeline

# List evolution progress
gryt evolution list v1.0.0

# Promote when ready
gryt generation promote v1.0.0
```

---

## Core Concepts

### Generation = Release Contract

A Generation declares what a version MUST contain before deployment.

```yaml
# .gryt/generations/v2.1.0.yaml
version: v2.1.0
description: "Q4 Payment Features"
changes:
  - type: add
    id: PAY-001
    title: "Apple Pay integration"
  - type: fix
    id: PAY-002
    title: "Race condition in webhook"
pipeline_template: release-pipeline
```

**Change Types:**
- `add` - New feature
- `fix` - Bug fix
- `refine` - Performance/UX improvement
- `remove` - Deprecation/removal

### Evolution = Proof of Change

An Evolution is a tagged pipeline run that proves one or more changes work.

```bash
# Create evolution for PAY-001
gryt evolution start v2.1.0 --change PAY-001

# This creates:
# - Evolution record in database
# - RC tag: v2.1.0-rc.1
# - Pipeline run with test results
```

### Promotion = Release Gate

Promotion validates all changes are proven before creating the final version tag.

**Default Gates:**
- All changes have at least one passing evolution
- No failed evolutions exist
- Minimum evolution count met (configurable)

---

## Pipeline Composition

### Basic Pipeline

```python
# pipeline_example.py
from gryt import Pipeline, CommandStep, LocalRuntime, SqliteData

# Define steps
test_step = CommandStep(
    name="test",
    command="go test ./...",
    description="Run unit tests"
)

build_step = CommandStep(
    name="build",
    command="go build -o bin/app",
    description="Build binary"
)

# Create pipeline
pipeline = Pipeline(
    name="ci-pipeline",
    steps=[test_step, build_step],
    parallel_runners=2
)

# Execute
runtime = LocalRuntime()
data = SqliteData(db_path=".gryt/gryt.db")

pipeline.execute(runtime, data)
```

### Language-Specific Steps

```python
from gryt import (
    GoModDownloadStep,
    GoBuildStep,
    GoTestStep,
    PytestStep,
    NpmInstallStep,
    CargoBuildStep
)

# Go pipeline
go_pipeline = Pipeline(
    name="go-ci",
    steps=[
        GoModDownloadStep(),
        GoTestStep(package="./..."),
        GoBuildStep(output="bin/app")
    ]
)

# Python pipeline
python_pipeline = Pipeline(
    name="python-ci",
    steps=[
        PipInstallStep(requirements="requirements.txt"),
        PytestStep(args="-v --cov=src")
    ]
)
```

### Parallel Execution

```python
# Run steps in parallel
pipeline = Pipeline(
    name="fast-ci",
    steps=[lint, test, security_scan],
    parallel_runners=3  # All steps run concurrently
)
```

### With Hooks

```python
from gryt import Pipeline, PrintHook, SlackDestination

# Define hooks
def on_failure(context):
    print(f"Pipeline {context['pipeline_name']} failed!")

pipeline = Pipeline(
    name="monitored-pipeline",
    steps=[test, build],
    hooks={
        "pipeline_fail": [PrintHook(), SlackDestination(webhook_url="...")]
    }
)
```

---

## Complete Workflow: Feature Release

### 1. Create Generation

```bash
gryt generation new v2.1.0
```

This creates:
- Database entry at `.gryt/gryt.db`
- YAML file at `.gryt/generations/v2.1.0.yaml`

### 2. Edit YAML and Update Database

Edit `.gryt/generations/v2.1.0.yaml`:
```yaml
version: v2.1.0
description: "Payment integration sprint"
changes:
  - type: add
    id: FEAT-101
    title: "Stripe Connect support"
  - type: fix
    id: BUG-42
    title: "Timeout on large transactions"
pipeline_template: release-pipeline
```

Sync changes to database:
```bash
gryt generation update v2.1.0
```

### 3. Prove First Change

```bash
# Start evolution
gryt evolution start v2.1.0 --change FEAT-101

# Implement feature, commit code
git add .
git commit -m "feat: add Stripe Connect support [FEAT-101]"

# Run pipeline
gryt run release-pipeline

# Pipeline creates v2.1.0-rc.1 tag on success
```

### 4. Prove Second Change

```bash
# Start next evolution
gryt evolution start v2.1.0 --change BUG-42

# Fix bug, commit
git add .
git commit -m "fix: handle large transaction timeouts [BUG-42]"

# Run pipeline
gryt run release-pipeline

# Creates v2.1.0-rc.2 tag
```

### 5. Check Progress

```bash
gryt evolution list v2.1.0
```

Output:
```
Generation: v2.1.0
Status: draft

Evolutions:
  v2.1.0-rc.1  FEAT-101  pass  2024-01-15 10:30
  v2.1.0-rc.2  BUG-42    pass  2024-01-15 14:20

Changes:
  FEAT-101  Stripe Connect support       proven
  BUG-42    Timeout on large transactions proven
```

### 6. Promote

```bash
gryt generation promote v2.1.0
```

This will:
- Run all promotion gates
- Create final tag `v2.1.0`
- Update generation status to `promoted`
- Trigger promotion hooks

---

## Pipeline Per Change

### Overview

Each change in a generation can have its own dedicated validation pipeline. This creates explicit linkage between changes and the tests that prove them.

### Generate Validation Pipelines

After defining changes in your generation YAML, generate validation pipeline scaffolds:

```bash
# Generate for all changes
gryt generation gen-test v2.1.0 --all

# Generate for specific change
gryt generation gen-test v2.1.0 --change FEAT-101
```

This creates pipeline files like:
```
.gryt/pipelines/
  v2_1_0_FEAT_101_VALIDATION_PIPELINE.py
  v2_1_0_BUG_42_VALIDATION_PIPELINE.py
```

### Pipeline Templates

Generated pipelines are type-specific:

**Add (New Feature)**
- Unit tests for new functionality
- Integration tests with existing system
- End-to-end user workflow tests
- Security scans
- Performance benchmarks

**Fix (Bug Fix)**
- Regression tests to verify bug is fixed
- Unit tests for fixed code
- Full test suite to prevent new regressions

**Refine (Improvement)**
- Performance benchmarks (before/after)
- Load tests
- Unit tests for refined code
- UX validation tests

**Remove (Deprecation)**
- Check for orphaned references
- Test replacement functionality
- Verify no broken dependencies

### Customize Generated Pipelines

Edit generated files to implement actual tests:

```python
# v2_1_0_FEAT_101_VALIDATION_PIPELINE.py

def create_pipeline() -> Pipeline:
    unit_test = CommandStep(
        name="unit_tests",
        command="pytest tests/test_stripe_connect.py -v",
        description="Test Stripe Connect integration"
    )

    integration_test = CommandStep(
        name="integration_tests",
        command="pytest tests/integration/test_payment_flow.py -v",
        description="Test full payment flow"
    )

    return Pipeline(
        name="FEAT_101_VALIDATION",
        steps=[unit_test, integration_test],
    )
```

### Link Changes to Pipelines in YAML

You can also manually specify pipelines in the generation YAML:

```yaml
version: v2.1.0
description: "Payment integration sprint"
changes:
  - type: add
    id: FEAT-101
    title: "Stripe Connect support"
    pipeline: v2_1_0_FEAT_101_VALIDATION_PIPELINE.py

  - type: fix
    id: BUG-42
    title: "Timeout on large transactions"
    pipeline: v2_1_0_BUG_42_VALIDATION_PIPELINE.py
```

Then run `gryt generation update v2.1.0` to sync to database.

---

## Hot-fix Workflow

### 1. Create Hot-fix

```bash
gryt audit hotfix v2.1.0 \
  --issue CRIT-99 \
  --title "Fix payment processing crash"
```

This creates `v2.1.1` generation automatically.

### 2. Implement and Test

```bash
# Start evolution
gryt evolution start v2.1.1 --change CRIT-99

# Fix the issue
git add .
git commit -m "fix: prevent crash in payment processor [CRIT-99]"

# Run pipeline
gryt run release-pipeline
```

### 3. Fast-track Promote

```bash
gryt audit hotfix-promote v2.1.1
```

Hot-fix uses minimal gates (only requires one passing evolution).

---

## Policy-Driven Workflows

### Define Policies

```yaml
# .gryt/policy.yaml
policies:
  - name: "e2e-tests-required"
    applies_to: [add, refine]
    required_steps:
      - e2e-tests
    description: "New features must have E2E tests"

  - name: "security-scan-required"
    applies_to: [add, fix, refine, remove]
    required_steps:
      - security-scan
    description: "All changes require security scan"

  - name: "performance-benchmark"
    applies_to: [refine]
    required_steps:
      - benchmark
    description: "Performance changes need benchmarks"
```

### Validate Against Policies

Policies are automatically validated when starting evolutions:

```bash
# This will fail if e2e-tests step is missing from pipeline
gryt evolution start v2.1.0 --change FEAT-101
```

---

## Using Templates

### Create Project from Template

```bash
# List available templates
gryt new list

# Create Go project
gryt new my-service --template go-release

# Creates:
# my-service/
#   .gryt/
#     gryt.db
#     generations/
#     pipelines/
#   main.go
#   go.mod
```

### Built-in Templates

- `go-release` - Go project with mod/test/build pipeline
- `python-ci` - Python with pytest and coverage
- `node-ci` - Node.js with npm test/build
- `minimal` - Bare minimum gryt structure

---

## Audit and Compliance

### Export Audit Trail

```bash
# JSON export
gryt audit export --output audit.json --format json

# CSV for spreadsheets
gryt audit export --output audit.csv --format csv

# HTML report
gryt audit export --output audit.html --format html
```

### Database Snapshots

```bash
# Create snapshot before risky operation
gryt audit snapshot --label "before-migration"

# List snapshots
gryt audit list-snapshots

# Rollback if needed
gryt audit rollback <snapshot-id>
```

### Compliance Report

```bash
# Generate NIST 800-161 compliance report
gryt compliance --output compliance-report.html
```

Report demonstrates:
- Change management practices
- Testing and validation
- Audit trail completeness
- Rollback capabilities
- Policy enforcement

---

## Advanced Patterns

### Multi-Change Evolution

Prove multiple changes in one evolution:

```bash
gryt evolution start v2.1.0 --change FEAT-101 --change BUG-42
```

### Custom Promotion Gates

```python
from gryt import PromotionGate, GateResult

class CodeCoverageGate(PromotionGate):
    def __init__(self, min_coverage: float):
        super().__init__("code_coverage")
        self.min_coverage = min_coverage

    def check(self, generation, data):
        # Query coverage from evolution data
        rows = data.query("""
            SELECT metric_value FROM data_rows
            WHERE metric_name = 'coverage'
            AND generation_id = ?
        """, (generation.generation_id,))

        if not rows:
            return GateResult(False, "No coverage data", {})

        coverage = float(rows[0]["metric_value"])
        if coverage < self.min_coverage:
            return GateResult(
                False,
                f"Coverage {coverage}% below minimum {self.min_coverage}%",
                {"coverage": coverage}
            )

        return GateResult(True, f"Coverage {coverage}% OK", {})

# Use in promotion
generation.promote(
    data,
    gates=[CodeCoverageGate(min_coverage=80.0)],
    auto_tag=True
)
```

### Custom Destinations

```python
from gryt import Destination

class S3Destination(Destination):
    def __init__(self, bucket: str, prefix: str):
        super().__init__("s3")
        self.bucket = bucket
        self.prefix = prefix

    def send(self, data: dict) -> bool:
        # Upload artifacts to S3
        import boto3
        s3 = boto3.client('s3')
        # ... upload logic
        return True

# Use in pipeline
pipeline = Pipeline(
    name="deploy-pipeline",
    steps=[build, test],
    destinations=[
        S3Destination(bucket="releases", prefix="v1.0.0/")
    ]
)
```

### Version Queries

```bash
# Query database directly
gryt db query "SELECT version, status, promoted_at FROM generations"

# Get metrics
gryt db metric pass_rate --gen v2.1.0

# Check evolution stats
gryt db query "SELECT COUNT(*) FROM evolutions WHERE status = 'pass'"
```

---

## Common Commands

```bash
# Initialization
gryt init                                    # Initialize .gryt/ structure
gryt new <project> --template <name>        # Create from template

# Generations
gryt generation new <version>                # Create generation contract
gryt generation update <version>             # Update DB from edited YAML file
gryt generation gen-test <version> --all     # Generate validation pipelines for all changes
gryt generation gen-test <version> -c <id>   # Generate validation pipeline for specific change
gryt generation list                         # List all generations
gryt generation show <version>               # Show generation details
gryt generation promote <version>            # Promote to production

# Evolutions
gryt evolution start <version> --change <id> # Start evolution
gryt evolution list <version>                # List generation's evolutions

# Pipelines
gryt run <pipeline>                          # Run pipeline
gryt pipeline list                           # List available pipelines

# Audit
gryt audit export -o <file> -f <format>      # Export audit trail
gryt audit snapshot -l <label>               # Create snapshot
gryt audit rollback <snapshot-id>            # Rollback database
gryt audit hotfix <base-version> -i <id>     # Create hot-fix

# Compliance
gryt compliance -o <file>                    # Generate compliance report

# Cloud Sync
gryt sync pull                               # Pull changes from cloud
gryt sync push                               # Push local changes to cloud
gryt sync push --version <version>           # Push specific version
gryt sync push --evolutions                  # Push completed evolutions
gryt sync status                             # Show sync status summary
gryt sync status --version <version>         # Show status for specific version
gryt sync config --mode <local|cloud|hybrid> # Set execution mode

# Database
gryt db query "<sql>"                        # Run SQL query
gryt db metric <name> --gen <version>        # Get metric

# Dashboard
gryt dashboard                               # Launch TUI dashboard
```

---

## Best Practices

### 1. Atomic Generations

Keep generations focused on a single release increment:

```yaml
# Good: Focused on one theme
version: v2.1.0
description: "Payment processing improvements"
changes:
  - add: Stripe integration
  - fix: Webhook race condition
  - refine: Payment flow UX

# Avoid: Too many unrelated changes
version: v2.1.0
changes:
  - add: Stripe integration
  - add: User profiles
  - add: Admin dashboard
  - fix: Email templates
```

### 2. Meaningful RC Tags

Each evolution should represent real progress:

```bash
# Good: One evolution per change
gryt evolution start v2.1.0 --change FEAT-101  # rc.1
gryt evolution start v2.1.0 --change FEAT-102  # rc.2

# Avoid: Multiple evolutions for same change without progress
# (Fix issues before creating new evolutions)
```

### 3. Use Policies

Enforce quality gates via policy instead of documentation:

```yaml
# .gryt/policy.yaml
policies:
  - name: "security-required"
    applies_to: [add, fix, refine, remove]
    required_steps: [security-scan, dependency-audit]
```

### 4. Snapshot Before Promotion

```bash
gryt audit snapshot --label "pre-v2.1.0-promotion"
gryt generation promote v2.1.0
```

### 5. Regular Audit Exports

```bash
# Weekly audit export for compliance
gryt audit export \
  --output "audit-$(date +%Y-%m-%d).json" \
  --format json
```

---

## Troubleshooting

### Evolution Fails to Start

```bash
# Check policy violations
gryt generation show v2.1.0

# Verify change exists in generation
cat .gryt/generations/v2.1.0.yaml
```

### Promotion Fails

```bash
# Check gate results
gryt generation promote v2.1.0  # Shows which gates failed

# Common issues:
# - Unproven changes: Create evolution for missing changes
# - Failed evolutions: Fix issues and create new passing evolution
# - Policy violations: Update pipeline to include required steps
```

### Database Corruption

```bash
# Rollback to last good snapshot
gryt audit list-snapshots
gryt audit rollback <snapshot-id>
```

### Pipeline Not Found

```bash
# List available pipelines
gryt pipeline list

# Check pipeline definition
cat .gryt/pipelines/<name>.yaml
```
