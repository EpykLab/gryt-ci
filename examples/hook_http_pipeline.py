from gryt import Pipeline, Runner, CommandStep, SqliteData, LocalRuntime, HttpHook

# Demonstrates HttpHook posting events to a remote service.
# Requires a reachable endpoint; if not available, the hook will ignore errors.

hook = HttpHook(
    base_url="http://localhost:8080",
    headers={"Content-Type": "application/json"},
    paths={
        "pipeline_start": "/hooks/pipeline/start",
        "pipeline_end": "/hooks/pipeline/end",
        "step_start": "/hooks/step/start",
        "step_end": "/hooks/step/end",
        "error": "/hooks/error",
    },
)

data = SqliteData(in_memory=True)
runtime = LocalRuntime()

runner = Runner([
    CommandStep('sample', {'cmd': ['echo', 'with http hook']}, data=data),
])

PIPELINE = Pipeline([runner], data=data, runtime=runtime, hook=hook)
