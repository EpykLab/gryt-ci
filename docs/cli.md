# CLI Usage

The gryt CLI is implemented in pure Python and exposed as the `gryt` command (installed via pip/pipx).

## Install (recommended via pipx)

- pipx install gryt  # once published to PyPI
- pipx install .     # from a local checkout

## .gryt Project Structure

When you initialize a project, gryt creates a hidden folder in your repo:

```
.gryt/
  gryt.db        # SQLite database
  config         # optional config placeholder
  pipelines/
    example.py   # sample pipeline (created by init)
```

- Default database path for CLI tooling is `./.gryt/gryt.db`.
- You can create multiple pipeline scripts under `.gryt/pipelines/`.

## Commands

- gryt init [path] [--force]
  - Initialize a new gryt project at `path` (default: current directory).
  - Creates `.gryt/` with `gryt.db`, `config`, and `pipelines/`.
  - `--force` will overwrite any existing `.gryt/` directory.

- gryt new --name NAME [--force] [--steps LIST]
  - Create a pipeline file `.gryt/pipelines/NAME.py` with a basic example workflow (shebang + imports included).
  - With `--steps`, you can quickly scaffold language-specific steps. Accepts a comma-separated list of presets: `go, python, js, docker, rust` (unknown tokens will generate placeholder CommandStep entries).
  - Use `--force` to overwrite if the file already exists.

- gryt run SCRIPT [--parallel]
  - Run a pipeline script.
  - SCRIPT can be a path to a Python file, or a bare name that resolves to `.gryt/pipelines/<name>.py`.
  - `--parallel` runs runners in parallel (ThreadPoolExecutor). Steps within a single runner remain sequential.

- gryt validate SCRIPT
  - Validate that the script exposes either a `PIPELINE` variable (gryt.Pipeline) or a `build() -> gryt.Pipeline` function.

- gryt env-validate SCRIPT
  - Validate the environment for a pipeline without running it. Aggregates all issues (no fail-fast) and prints a JSON report.

- gryt db [--db PATH]
  - Dump the SQLite database contents to stdout as JSON for easy piping to other tools.
  - Defaults to `./.gryt/gryt.db` if `--db` is not provided.

## Examples

Initialize and run using the installed command:
```
gryt init --force
gryt new --name example
# scaffold with presets
gryt new --name myproj --steps go,python,js
# run by bare name (resolves to .gryt/pipelines/example.py)
gryt validate example
gryt run example
# or run by path
gryt run .gryt/pipelines/example.py
# inspect DB
gryt db > dump.json
```

Alternative (module form still works):
```
python -m gryt.cli run .gryt/pipelines/example.py
```

## Script Conventions

Your pipeline script must either:

- Define `PIPELINE` as an instance of `gryt.Pipeline`, or
- Define a function `build() -> gryt.Pipeline`.

Example:
```python
from gryt import Pipeline, Runner, CommandStep, SqliteData, LocalRuntime

data = SqliteData(db_path='.gryt/gryt.db')
runtime = LocalRuntime()

runner = Runner([
    CommandStep('hello', {'cmd': ['echo', 'hello']}, data=data),
    CommandStep('world', {'cmd': ['echo', 'world']}, data=data),
])

PIPELINE = Pipeline([runner], data=data, runtime=runtime)
```
