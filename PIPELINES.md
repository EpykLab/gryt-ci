# Pipeline Composition Guide

How to build, compose, and orchestrate pipelines in gryt-ci.

---

## Basic Pipeline Structure

```python
from gryt import Pipeline, CommandStep, LocalRuntime, SqliteData

# Create steps
step1 = CommandStep(name="test", command="go test ./...")
step2 = CommandStep(name="build", command="go build")

# Compose pipeline
pipeline = Pipeline(
    name="basic-ci",
    steps=[step1, step2]
)

# Execute
runtime = LocalRuntime()
data = SqliteData(db_path=".gryt/gryt.db")
pipeline.execute(runtime, data)
```

**Key Components:**
- **Steps:** Atomic executable actions
- **Pipeline:** Ordered or parallel collection of steps
- **Runtime:** Execution environment (Local, Docker, etc.)
- **Data:** SQLite database for results and audit

---

## Step Types

### CommandStep

Basic shell command execution.

```python
from gryt import CommandStep

test_step = CommandStep(
    name="unit-tests",
    command="pytest tests/ -v",
    description="Run unit tests with pytest"
)

lint_step = CommandStep(
    name="lint",
    command="pylint src/",
    description="Check code quality"
)
```

### Language-Specific Steps

Pre-built steps for common operations.

```python
from gryt import (
    GoModDownloadStep,
    GoBuildStep,
    GoTestStep,
    PipInstallStep,
    PytestStep,
    NpmInstallStep,
    NpmBuildStep,
    CargoBuildStep,
    CargoTestStep
)

# Go
go_download = GoModDownloadStep()
go_test = GoTestStep(package="./...", args="-v -race")
go_build = GoBuildStep(output="bin/myapp", ldflags="-s -w")

# Python
pip_install = PipInstallStep(requirements="requirements.txt")
pytest = PytestStep(args="--cov=src --cov-report=html")

# JavaScript
npm_install = NpmInstallStep()
npm_build = NpmBuildStep(script="build:prod")

# Rust
cargo_build = CargoBuildStep(release=True)
cargo_test = CargoTestStep(args="--all-features")
```

### Custom Steps

Extend `Step` base class for custom logic.

```python
from gryt import Step
from typing import Dict, Any

class DatabaseMigrationStep(Step):
    def __init__(self, migration_dir: str):
        super().__init__(name="db-migration")
        self.migration_dir = migration_dir

    def execute(self, runtime, context: Dict[str, Any]) -> bool:
        """Run database migrations"""
        import subprocess

        result = subprocess.run(
            ["migrate", "-path", self.migration_dir, "-database",
             context.get("db_url", ""), "up"],
            capture_output=True,
            text=True
        )

        # Store output in context
        context["migration_output"] = result.stdout

        return result.returncode == 0

# Usage
migration_step = DatabaseMigrationStep(migration_dir="./migrations")
```

---

## Execution Modes

### Sequential Execution

Steps run one after another (default).

```python
pipeline = Pipeline(
    name="sequential-ci",
    steps=[
        CommandStep("download", "go mod download"),
        CommandStep("test", "go test ./..."),
        CommandStep("build", "go build"),
        CommandStep("package", "tar -czf app.tar.gz bin/")
    ]
)
```

**Execution order:** download -> test -> build -> package

### Parallel Execution

All steps run concurrently.

```python
pipeline = Pipeline(
    name="parallel-ci",
    steps=[
        CommandStep("lint", "golint ./..."),
        CommandStep("test", "go test ./..."),
        CommandStep("security", "gosec ./...")
    ],
    parallel_runners=3  # All 3 steps run at once
)
```

**Benefits:**
- Faster execution
- Independent validation
- Resource utilization

**When to use:**
- Steps are independent
- No shared state
- Validation steps (lint, test, security)

### Mixed Execution

Combine sequential and parallel.

```python
# Phase 1: Setup (sequential)
setup = Pipeline(
    name="setup",
    steps=[
        CommandStep("deps", "go mod download"),
        CommandStep("generate", "go generate ./...")
    ]
)

# Phase 2: Validation (parallel)
validation = Pipeline(
    name="validation",
    steps=[
        CommandStep("lint", "golint ./..."),
        CommandStep("test", "go test ./..."),
        CommandStep("security", "gosec ./...")
    ],
    parallel_runners=3
)

# Phase 3: Build (sequential)
build = Pipeline(
    name="build",
    steps=[
        CommandStep("build", "go build"),
        CommandStep("package", "tar -czf app.tar.gz bin/")
    ]
)

# Execute in order
setup.execute(runtime, data)
validation.execute(runtime, data)
build.execute(runtime, data)
```

---

## Data Flow and Context

### Passing Data Between Steps

```python
class FetchVersionStep(Step):
    def execute(self, runtime, context: Dict[str, Any]) -> bool:
        # Read version from file
        with open("VERSION", "r") as f:
            version = f.read().strip()

        # Store in context
        context["app_version"] = version
        return True

class BuildWithVersionStep(Step):
    def execute(self, runtime, context: Dict[str, Any]) -> bool:
        # Read version from context
        version = context.get("app_version", "unknown")

        # Use in build
        result = subprocess.run(
            ["go", "build", "-ldflags", f"-X main.version={version}"],
            capture_output=True
        )

        return result.returncode == 0

# Pipeline shares context across steps
pipeline = Pipeline(
    name="versioned-build",
    steps=[
        FetchVersionStep(),
        BuildWithVersionStep()
    ]
)
```

### Storing Results in Database

```python
class BenchmarkStep(Step):
    def execute(self, runtime, context: Dict[str, Any]) -> bool:
        result = subprocess.run(
            ["go", "test", "-bench=.", "-benchmem"],
            capture_output=True,
            text=True
        )

        # Parse benchmark output
        # ... parsing logic ...
        ops_per_sec = 1000000

        # Store in database
        data = context.get("data")
        if data:
            data.insert("benchmarks", {
                "pipeline_id": context.get("pipeline_id"),
                "metric": "ops_per_sec",
                "value": ops_per_sec,
                "timestamp": datetime.now().isoformat()
            })

        return result.returncode == 0
```

---

## Hooks and Events

### Pipeline Lifecycle Hooks

```python
from gryt import Pipeline, PrintHook

def on_pipeline_start(context):
    print(f"Starting pipeline: {context['pipeline_name']}")
    # Send Slack notification, etc.

def on_pipeline_complete(context):
    print(f"Pipeline completed: {context['status']}")

def on_step_fail(context):
    print(f"Step failed: {context['step_name']}")
    # Alert on-call engineer

pipeline = Pipeline(
    name="monitored-pipeline",
    steps=[test, build],
    hooks={
        "pipeline_start": [on_pipeline_start],
        "pipeline_complete": [on_pipeline_complete],
        "step_fail": [on_step_fail]
    }
)
```

**Available Hooks:**
- `pipeline_start` - Before first step
- `pipeline_complete` - After last step
- `pipeline_fail` - If any step fails
- `step_start` - Before each step
- `step_complete` - After each step
- `step_fail` - If step fails

### Built-in Hook Types

```python
from gryt import PrintHook, HttpHook, SlackDestination

pipeline = Pipeline(
    name="hooked-pipeline",
    steps=[test, build],
    hooks={
        "pipeline_fail": [
            PrintHook(),  # Print to console
            HttpHook(url="https://api.example.com/alerts"),  # HTTP POST
            SlackDestination(webhook_url="https://hooks.slack.com/...")
        ]
    }
)
```

---

## Validation and Environment Checks

### Pre-flight Validation

```python
from gryt import EnvVarValidator, ToolValidator

# Ensure required environment variables exist
env_validator = EnvVarValidator(
    required_vars=["DATABASE_URL", "API_KEY", "ENVIRONMENT"]
)

# Ensure required tools are installed
tool_validator = ToolValidator(
    required_tools=["docker", "kubectl", "helm"]
)

# Validate before running pipeline
if not env_validator.validate():
    print("Missing environment variables")
    exit(1)

if not tool_validator.validate():
    print("Missing required tools")
    exit(1)

pipeline.execute(runtime, data)
```

### Scythe Validator Integration

```python
from gryt import ScytheValidator

# Validate using Scythe (design-by-contract validation)
scythe = ScytheValidator(
    contract_file="contracts/pipeline.scythe"
)

if scythe.validate(pipeline):
    pipeline.execute(runtime, data)
else:
    print("Pipeline violates contract")
```

---

## Publishing Artifacts

### Destinations

```python
from gryt import (
    NpmRegistryDestination,
    PyPIDestination,
    GitHubReleaseDestination,
    ContainerRegistryDestination,
    S3Destination
)

# Publish to npm
npm_dest = NpmRegistryDestination(
    registry="https://registry.npmjs.org",
    token="${NPM_TOKEN}"
)

# Publish to PyPI
pypi_dest = PyPIDestination(
    repository="https://upload.pypi.org/legacy/",
    token="${PYPI_TOKEN}"
)

# Create GitHub release
github_dest = GitHubReleaseDestination(
    repo="owner/repo",
    token="${GITHUB_TOKEN}"
)

# Push container image
container_dest = ContainerRegistryDestination(
    registry="ghcr.io",
    image="owner/app",
    tag="${VERSION}"
)

# Attach to pipeline
pipeline = Pipeline(
    name="publish-pipeline",
    steps=[build, test],
    destinations=[npm_dest, github_dest]
)
```

### Conditional Publishing

```python
class PublishStep(Step):
    def execute(self, runtime, context: Dict[str, Any]) -> bool:
        # Only publish on main branch
        branch = os.getenv("GIT_BRANCH", "")
        if branch != "main":
            print("Skipping publish (not on main)")
            return True

        # Only publish if version tag
        tag = os.getenv("GIT_TAG", "")
        if not tag.startswith("v"):
            print("Skipping publish (not a version tag)")
            return True

        # Publish
        result = subprocess.run(["npm", "publish"], capture_output=True)
        return result.returncode == 0
```

---

## Complete Pipeline Examples

### Go Microservice

```python
from gryt import (
    Pipeline,
    GoModDownloadStep,
    GoTestStep,
    GoBuildStep,
    CommandStep,
    ContainerRegistryDestination
)

# Dependencies
deps = GoModDownloadStep()

# Code generation
generate = CommandStep(
    name="generate",
    command="go generate ./..."
)

# Linting
lint = CommandStep(
    name="lint",
    command="golangci-lint run --timeout 5m"
)

# Testing
test = GoTestStep(
    package="./...",
    args="-v -race -coverprofile=coverage.out"
)

# Security scan
security = CommandStep(
    name="security",
    command="gosec -fmt json -out results.json ./..."
)

# Build binary
build = GoBuildStep(
    output="bin/api-server",
    ldflags="-s -w -X main.version=${VERSION}"
)

# Build container
container = CommandStep(
    name="container",
    command="docker build -t myapi:${VERSION} ."
)

# Compose pipeline
pipeline = Pipeline(
    name="go-microservice-ci",
    steps=[
        deps,
        generate,
        lint,
        test,
        security,
        build,
        container
    ],
    destinations=[
        ContainerRegistryDestination(
            registry="ghcr.io",
            image="owner/myapi",
            tag="${VERSION}"
        )
    ]
)
```

### Python Web App

```python
from gryt import (
    Pipeline,
    PipInstallStep,
    PytestStep,
    CommandStep
)

# Install dependencies
install = PipInstallStep(
    requirements="requirements.txt"
)

# Lint with black
lint = CommandStep(
    name="black",
    command="black --check src/"
)

# Type checking
typecheck = CommandStep(
    name="mypy",
    command="mypy src/"
)

# Testing
test = PytestStep(
    args="--cov=src --cov-report=html --cov-report=term"
)

# Security scan
security = CommandStep(
    name="bandit",
    command="bandit -r src/ -f json -o security.json"
)

# Build package
build = CommandStep(
    name="build",
    command="python -m build"
)

pipeline = Pipeline(
    name="python-web-ci",
    steps=[install, lint, typecheck, test, security, build],
    destinations=[
        PyPIDestination(
            repository="https://upload.pypi.org/legacy/",
            token="${PYPI_TOKEN}"
        )
    ]
)
```

### Full-Stack Application

```python
# Backend (Go)
backend_pipeline = Pipeline(
    name="backend",
    steps=[
        GoModDownloadStep(),
        GoTestStep(package="./..."),
        GoBuildStep(output="bin/api")
    ]
)

# Frontend (React)
frontend_pipeline = Pipeline(
    name="frontend",
    steps=[
        NpmInstallStep(),
        CommandStep("lint", "npm run lint"),
        CommandStep("test", "npm run test:ci"),
        NpmBuildStep(script="build")
    ]
)

# E2E Tests (after both built)
e2e_pipeline = Pipeline(
    name="e2e",
    steps=[
        CommandStep("start-services", "docker-compose up -d"),
        CommandStep("wait", "sleep 10"),
        CommandStep("test", "npm run test:e2e"),
        CommandStep("stop-services", "docker-compose down")
    ]
)

# Execute in order
backend_pipeline.execute(runtime, data)
frontend_pipeline.execute(runtime, data)
e2e_pipeline.execute(runtime, data)
```

### Multi-Environment Deployment

```python
class DeployStep(Step):
    def __init__(self, environment: str):
        super().__init__(name=f"deploy-{environment}")
        self.environment = environment

    def execute(self, runtime, context: Dict[str, Any]) -> bool:
        version = context.get("version", "latest")

        # Deploy to environment
        result = subprocess.run([
            "kubectl", "set", "image",
            f"deployment/app-{self.environment}",
            f"app=myapp:{version}",
            "--namespace", self.environment
        ], capture_output=True)

        return result.returncode == 0

# Build once
build_pipeline = Pipeline(
    name="build",
    steps=[test, build, container]
)

# Deploy to multiple environments
deploy_staging = Pipeline(
    name="deploy-staging",
    steps=[DeployStep("staging")]
)

deploy_production = Pipeline(
    name="deploy-production",
    steps=[DeployStep("production")]
)

# Execute
build_pipeline.execute(runtime, data)
deploy_staging.execute(runtime, data)

# Manual approval before production
input("Deploy to production? [Enter]")
deploy_production.execute(runtime, data)
```

---

## Error Handling

### Fail Fast vs Continue

```python
# Fail fast (default)
# Pipeline stops on first failure
pipeline = Pipeline(
    name="fail-fast",
    steps=[lint, test, build]
)

# Continue on error
# Run all steps, report failures at end
pipeline = Pipeline(
    name="continue-on-error",
    steps=[lint, test, build],
    fail_fast=False  # Custom implementation
)
```

### Retry Logic

```python
class RetryableStep(Step):
    def __init__(self, name: str, command: str, retries: int = 3):
        super().__init__(name=name)
        self.command = command
        self.retries = retries

    def execute(self, runtime, context: Dict[str, Any]) -> bool:
        for attempt in range(self.retries):
            result = subprocess.run(
                self.command,
                shell=True,
                capture_output=True
            )

            if result.returncode == 0:
                return True

            print(f"Attempt {attempt + 1} failed, retrying...")
            time.sleep(2 ** attempt)  # Exponential backoff

        return False

# Flaky test that might need retries
flaky_test = RetryableStep(
    name="integration-tests",
    command="npm run test:integration",
    retries=3
)
```

---

## Performance Optimization

### Caching Dependencies

```python
class CachedGoModStep(Step):
    def execute(self, runtime, context: Dict[str, Any]) -> bool:
        # Check if go.sum changed
        import hashlib

        go_sum_hash = hashlib.md5(
            open("go.sum", "rb").read()
        ).hexdigest()

        cache_key = f"gomod-{go_sum_hash}"
        cache_dir = f".gryt/cache/{cache_key}"

        # Use cached if exists
        if os.path.exists(cache_dir):
            shutil.copytree(cache_dir, "vendor")
            return True

        # Download and cache
        result = subprocess.run(
            ["go", "mod", "download"],
            capture_output=True
        )

        if result.returncode == 0:
            os.makedirs(cache_dir, exist_ok=True)
            shutil.copytree("vendor", cache_dir)

        return result.returncode == 0
```

### Incremental Builds

```python
class IncrementalBuildStep(Step):
    def execute(self, runtime, context: Dict[str, Any]) -> bool:
        # Only rebuild changed packages
        result = subprocess.run(
            ["go", "build", "-i", "-o", "bin/app"],
            capture_output=True
        )
        return result.returncode == 0
```

---

## Testing Pipelines

```python
# test_pipeline.py
import unittest
from gryt import Pipeline, CommandStep, LocalRuntime, SqliteData

class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.runtime = LocalRuntime()
        self.data = SqliteData(db_path=":memory:")

    def test_pipeline_succeeds(self):
        pipeline = Pipeline(
            name="test-pipeline",
            steps=[
                CommandStep("test", "echo 'hello'")
            ]
        )

        result = pipeline.execute(self.runtime, self.data)
        self.assertTrue(result)

    def test_pipeline_fails_on_error(self):
        pipeline = Pipeline(
            name="failing-pipeline",
            steps=[
                CommandStep("fail", "exit 1")
            ]
        )

        result = pipeline.execute(self.runtime, self.data)
        self.assertFalse(result)

    def tearDown(self):
        self.data.close()
```

---

## Best Practices

### 1. Keep Steps Atomic

```python
# Good: Each step does one thing
steps = [
    CommandStep("lint", "golint ./..."),
    CommandStep("test", "go test ./..."),
    CommandStep("build", "go build")
]

# Avoid: Multiple operations in one step
steps = [
    CommandStep("all", "golint ./... && go test ./... && go build")
]
```

### 2. Use Descriptive Names

```python
# Good
CommandStep(
    name="unit-tests-with-coverage",
    command="go test -coverprofile=coverage.out ./...",
    description="Run unit tests and generate coverage report"
)

# Avoid
CommandStep(name="test", command="go test ./...")
```

### 3. Fail Early

```python
# Put fast checks first
pipeline = Pipeline(
    name="optimized-ci",
    steps=[
        CommandStep("fmt-check", "gofmt -l ."),      # Fast
        CommandStep("lint", "golint ./..."),         # Fast
        CommandStep("test", "go test ./..."),        # Slower
        CommandStep("integration", "npm run test:e2e")  # Slowest
    ]
)
```

### 4. Parallelize Independent Steps

```python
# Validation can run in parallel
validation = Pipeline(
    name="validation",
    steps=[
        CommandStep("lint", "golint ./..."),
        CommandStep("security", "gosec ./..."),
        CommandStep("license-check", "license-checker")
    ],
    parallel_runners=3
)
```

### 5. Store Artifacts

```python
class ArtifactStep(Step):
    def execute(self, runtime, context: Dict[str, Any]) -> bool:
        # Store build artifacts in database
        data = context.get("data")
        pipeline_id = context.get("pipeline_id")

        data.insert("artifacts", {
            "pipeline_id": pipeline_id,
            "type": "binary",
            "path": "bin/app",
            "size_bytes": os.path.getsize("bin/app"),
            "checksum": self._calculate_checksum("bin/app")
        })

        return True
```

---

## Summary

**Basic Building Blocks:**
- CommandStep for shell commands
- Language-specific steps (Go, Python, Node, Rust)
- Custom steps extending Step base class

**Execution Strategies:**
- Sequential for dependent steps
- Parallel for independent validation
- Mixed for complex workflows

**Integration:**
- Hooks for monitoring and alerts
- Destinations for artifact publishing
- Validators for pre-flight checks

**Optimization:**
- Caching for dependencies
- Incremental builds
- Fail fast ordering

**Best Practices:**
- Atomic steps
- Descriptive naming
- Early validation
- Parallel execution
- Artifact storage
