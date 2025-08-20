# Hooks

Hooks allow you to observe and extend pipeline and step execution. They are ideal for sending or retrieving data from remote services (e.g., HTTP endpoints) or for emitting custom logs.

Key properties:
- Optional: Steps and Pipelines can take a `hook` argument; if a Pipeline has a hook, it will be injected into its Steps unless those Steps already have their own hooks.
- Robust: Hooks are best-effort; exceptions raised inside hook callbacks are caught and suppressed to keep the run resilient.

## API

The base class:

```python
from gryt import Hook

class Hook:
    def on_pipeline_start(self, pipeline, context=None): ...
    def on_pipeline_end(self, pipeline, results: dict, context=None): ...
    def on_step_start(self, step, context=None): ...
    def on_step_end(self, step, result: dict, context=None): ...
    def on_error(self, scope: str, error: Exception, context=None): ...
```

- scope is one of: "pipeline", "step".
- All callbacks are optional; base implementations are no-ops and swallow errors.

## Built-in Hooks

- PrintHook: logs lifecycle events to stdout/stderr.
- HttpHook: posts JSON events to a remote HTTP endpoint using the Python standard library.

### PrintHook example

```python
from gryt import Pipeline, Runner, CommandStep, SqliteData, LocalRuntime, PrintHook

hook = PrintHook()

data = SqliteData(in_memory=True)
runtime = LocalRuntime()
runner = Runner([
    CommandStep('hello', {'cmd': ['echo', 'hello']}, data=data),
    CommandStep('world', {'cmd': ['echo', 'world']}, data=data),
])

PIPELINE = Pipeline([runner], data=data, runtime=runtime, hook=hook)
```

### HttpHook example

```python
from gryt import Pipeline, Runner, CommandStep, SqliteData, LocalRuntime, HttpHook

hook = HttpHook(
    base_url="http://localhost:8080",
    headers={"Authorization": "Bearer <token>", "Content-Type": "application/json"},
    paths={
        "pipeline_start": "/ci/pipeline/start",
        "pipeline_end": "/ci/pipeline/end",
        "step_start": "/ci/step/start",
        "step_end": "/ci/step/end",
        "error": "/ci/error",
    },
)

data = SqliteData(in_memory=True)
runtime = LocalRuntime()
runner = Runner([
    CommandStep('unit_tests', {'cmd': ['pytest', '-q']}, data=data),
])

PIPELINE = Pipeline([runner], data=data, runtime=runtime, hook=hook)
```

Note: HttpHook uses urllib and will ignore connectivity errors (it will not fail the pipeline).

## Step-level Hooks

You can also attach a hook to a specific Step:

```python
from gryt import CommandStep, PrintHook

step = CommandStep('greet', {'cmd': ['echo', 'hi']}, hook=PrintHook())
```

If both Pipeline and Step have hooks, the Step's own hook is used for that step.
