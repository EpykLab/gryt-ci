# Steps Catalog

This catalog describes the ready-to-use Steps bundled with gryt. All Steps return a structured dict and most are thin wrappers around `CommandStep`.

Import options:
- Top-level: `from gryt import NpmInstallStep` (aggregated re-exports)
- Namespaced: `from gryt.languages.node import NpmInstallStep`

## Common Config Options
Most steps accept these standard options via `config`:
- `cwd`: working directory for the command.
- `env`: dict of environment variables.
- `timeout`: command timeout (seconds).
- `retries`: retry count on failure (0 default).

## Golang
- `GoModDownloadStep(id, config={ 'cwd': str, 'env': dict, 'timeout': float, 'retries': int })`
  - Runs `go mod download`.
- `GoBuildStep(id, config={ 'packages': [str] (default ['./...']), 'flags': [str], 'output': str, ... })`
  - Runs `go build` with optional flags and output.
- `GoTestStep(id, config={ 'packages': [str] (default ['./...']), 'flags': [str], 'json': bool, ... })`
  - Runs `go test` with optional `-json`.

## Python
- `PipInstallStep(id, config={ 'requirements': str, 'packages': [str], 'upgrade': bool, 'user': bool, ... })`
  - Installs Python packages using pip. If `requirements` is set, uses `-r`.
- `PytestStep(id, config={ 'args': [str], 'paths': [str], ... })`
  - Runs `pytest` with additional arguments and paths.

## Node / Svelte
- `NpmInstallStep(id, config={ 'use_ci': bool (default True), ... })`
  - Uses `npm ci` when a lockfile is present and not disabled, otherwise `npm install`.
- `SvelteBuildStep(id, config={ 'script': str (default 'build'), ... })`
  - Runs `npm run <script>`.

## Rust
- `CargoBuildStep(id, config={ 'release': bool, 'all_features': bool, 'features': [str], 'target': str, ... })`
  - Runs `cargo build` with optional flags.
- `CargoTestStep(id, config={ 'release': bool, 'workspace': bool, 'all_features': bool, 'features': [str], ... })`
  - Runs `cargo test` with optional flags.

## Containers
- `ContainerBuildStep(id, config={ 'context_path': str, 'dockerfile': str='Dockerfile', 'tags': [str]|str, 'build_args': dict, 'labels': dict, 'platform': str, 'target': str, 'network': str, 'pull': bool, 'push': bool })`
  - Builds a container image using the Docker SDK for Python (no shell calls). If the SDK or daemon is unavailable, returns a structured error with guidance. Optional push via the SDK.
  - Note: The Docker SDK for Python is an optional dependency. Install with `pip install docker` in your environment.

## Notes
- Live output streaming: when you run pipelines with `gryt run ... --show`, most steps that wrap shell commands stream their stdout/stderr live to your terminal. This includes CommandStep and language wrappers (Go, Node, Python, Rust). ContainerBuildStep also streams Docker build/push output via the SDK.
- Steps store their results to the `steps_output` table by default when a Data instance is attached to the Step (either directly or via Runner). For command-like steps, stdout and stderr are also saved in dedicated `stdout`/`stderr` columns (in addition to the full structured `output_json`).
- Choose unique Step ids to avoid primary key collisions when using a persistent DB.
- Steps can take an optional `hook` to send lifecycle events to logs or remote services. See docs/hooks.md.
