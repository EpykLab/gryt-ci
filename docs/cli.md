# CLI Usage

The gryt CLI is implemented in pure Python and exposed as the `gryt` command (installed via pip/pipx).

## Install (recommended via pipx)

- pipx install gryt  # once published to PyPI
- pipx install .     # from a local checkout

## Commands

- gryt init [path]
  - Create a sample `pipeline.py` in the given path (defaults to current directory).
  - Use `--force` to overwrite an existing file.

- gryt validate <script.py>
  - Validate that the provided Python script exposes either:
    - a `PIPELINE` variable of type `gryt.Pipeline`, or
    - a callable `build()` that returns a `gryt.Pipeline`.

- gryt run <script.py> [--parallel]
  - Execute the pipeline defined in the given script.
  - `--parallel` runs runners in parallel (using a thread pool). Steps within a single runner are still sequential.

## Examples

Using the installed command:
```
gryt init --force
gryt validate pipeline.py
gryt run pipeline.py
```

Alternative (module form still works):
```
python -m gryt.cli run pipeline.py
```

## Script Conventions

Your pipeline script must either:

- Define `PIPELINE` as an instance of `gryt.Pipeline`, or
- Define a function `build() -> gryt.Pipeline`.

Example:
```python
from gryt import Pipeline, Runner, CommandStep, SqliteData, LocalRuntime

data = SqliteData(db_path='.gryt.db')
runtime = LocalRuntime()

runner = Runner([
    CommandStep('hello', {'cmd': ['echo', 'hello']}, data=data),
    CommandStep('world', {'cmd': ['echo', 'world']}, data=data),
])

PIPELINE = Pipeline([runner], data=data, runtime=runtime)
```
