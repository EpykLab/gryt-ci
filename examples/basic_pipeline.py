from gryt import Pipeline, Runner, CommandStep, SqliteData, LocalRuntime

# Minimal, runnable everywhere example

data = SqliteData(in_memory=True)  # in-memory DB avoids file persistence during local dev
runtime = LocalRuntime()

runner = Runner([
    CommandStep('hello', {'cmd': ['echo', 'hello']}, data=data),
    CommandStep('world', {'cmd': ['echo', 'world']}, data=data),
])

from gryt import PrintHook

hook = PrintHook()

PIPELINE = Pipeline([runner], data=data, runtime=runtime, hook=hook)
