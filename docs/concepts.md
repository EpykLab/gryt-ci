# Concepts

This section covers the primitives that make up gryt.

## Data (SqliteData)
- SQLite-backed, thread-safe data store.
- JSON-friendly inserts: dict/list values are serialized automatically.
- Default DB path with CLI: `.gryt/gryt.db` (or `:memory:` when in-memory). The class default is `.gryt.db` if you don’t pass a path.
- Predefined tables are auto-created: `pipelines`, `runners`, `steps_output`, `versions`.
- Common table for step outputs: `steps_output` with columns: `step_id TEXT PRIMARY KEY`, `runner_id TEXT`, `name TEXT`, `output_json TEXT`, `status TEXT`, `duration REAL`, `timestamp DATETIME DEFAULT CURRENT_TIMESTAMP`.

Tip: If you re-run a pipeline using the same step ids into the same DB file, `steps_output.step_id` may conflict (PRIMARY KEY). Use distinct step ids, delete/rotate the DB, or switch to in-memory for dev runs.

## Step and CommandStep
- Step is an abstract unit of work with a `run() -> dict` method.
- CommandStep runs a shell command (list form), captures stdout/stderr, return code, duration, and attempts (with basic retry support via `retries`).
- Most higher-level steps compose CommandStep for their actual execution.

## Runner
- Executes a sequence of Steps.
- `fail_fast` (default True) stops further execution on first error.
- Shares a single Data instance across steps (if provided), enabling data persistence.

## Pipeline
- Composes one or more Runners.
- Optional parallel execution: runs Runners concurrently using threads.
- Can be provided a `Runtime` to provision/teardown an environment around the run.
- Optional Hook to observe pipeline lifecycle and step events.
- Optional Destinations to publish artifacts after execution. Pass artifacts via `execute(artifacts=[...])`.

## Runtime
- Abstract provisioning interface.
- The MVP includes a `LocalRuntime` stub that does not install anything automatically.
- Use Steps to perform any environment configuration you need.

## Versioning
- `SimpleVersioning` implements a minimal semver bump based on the latest git tag.
- You can call `bump_version(level)` and `tag_release(version, message)` outside pipeline execution (e.g., in a release script).

## Environment Validation
- Optional validators can be attached to a Pipeline to check the environment before any steps run.
- Validators aggregate all issues (no fail-fast). If any issues are found, the pipeline returns a report and does not execute steps.
- Built-ins include:
  - EnvVarValidator(required=[...]) to check required vars like GITHUB_TOKEN or NPM_TOKEN.
  - ToolValidator(tools=[...]) to verify tools exist (and optionally meet a minimum version), e.g., npm, twine, cargo, go.
- You can also run validation via CLI without running the pipeline:
  - `gryt env-validate <SCRIPT>`
