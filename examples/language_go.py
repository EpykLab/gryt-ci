from gryt import Pipeline, Runner, SqliteData, LocalRuntime
from gryt import GoModDownloadStep, GoBuildStep, GoTestStep

# Demonstrates Go steps.
# Requires Go toolchain installed and a Go module in cwd.


data = SqliteData(in_memory=True)
runtime = LocalRuntime()

runner = Runner([
    GoModDownloadStep('go_mod_download', {'cwd': '.'}),
    GoBuildStep('go_build', {'cwd': '.', 'packages': ['./...']}),
    GoTestStep('go_test', {'cwd': '.', 'packages': ['./...'], 'json': False}),
], data=data)

PIPELINE = Pipeline([runner], data=data, runtime=runtime)
