from gryt import Pipeline, Runner, CommandStep, SqliteData, LocalRuntime

# Demonstrates multiple runners and the CLI --parallel flag.
# Run with: python -m gryt.cli run examples/parallel_pipeline.py --parallel

data = SqliteData(in_memory=True)
runtime = LocalRuntime()

runner_a = Runner([
    CommandStep('a1', {'cmd': ['echo', 'runner A - step 1']}, data=data),
    CommandStep('a2', {'cmd': ['echo', 'runner A - step 2']}, data=data),
])

runner_b = Runner([
    CommandStep('b1', {'cmd': ['echo', 'runner B - step 1']}, data=data),
    CommandStep('b2', {'cmd': ['echo', 'runner B - step 2']}, data=data),
])

PIPELINE = Pipeline([runner_a, runner_b], data=data, runtime=runtime)
