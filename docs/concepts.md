# Concepts

This section covers the primitives that make up gryt.

## Data (SqliteData)
- SQLite-backed, thread-safe data store.
- JSON-friendly inserts: dict/list values are serialized automatically.
- Default DB file: `.gryt.db` in the working directory (or `:memory:` when in-memory).
- Common table for step outputs: `steps_output` with columns:
  - `id TEXT PRIMARY KEY` (step id)
  - `result TEXT` (JSON string)
  - `timestamp DATETIME DEFAULT CURRENT_TIMESTAMP`

Tip: If you re-run a pipeline using the same step ids into the same DB file, inserts may fail due to the primary key constraint. Use distinct step ids, delete/rotate the DB, or switch to in-memory for dev runs.

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
