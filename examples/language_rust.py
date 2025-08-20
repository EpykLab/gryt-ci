from gryt import Pipeline, Runner, SqliteData, LocalRuntime
from gryt import CargoBuildStep, CargoTestStep

# Demonstrates Rust steps.
# Requires Rust toolchain (`cargo`) installed and a Cargo project in cwd.


data = SqliteData(in_memory=True)
runtime = LocalRuntime()

runner = Runner([
    CargoBuildStep('cargo_build', {'cwd': '.', 'release': False}),
    CargoTestStep('cargo_test', {'cwd': '.', 'workspace': False}),
], data=data)

PIPELINE = Pipeline([runner], data=data, runtime=runtime)
