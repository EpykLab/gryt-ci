from gryt import Pipeline, Runner, SqliteData, LocalRuntime
from gryt import PipInstallStep, PytestStep

# Demonstrates Python-specific steps.
# NOTE: Requires `pytest` to be available on PATH for PytestStep to succeed.
# You can uncomment the PipInstallStep to install pytest for the local user.


data = SqliteData(in_memory=True)
runtime = LocalRuntime()

steps = [
    # PipInstallStep('install_pytest', {'packages': ['pytest'], 'user': True}),
    PytestStep('pytest', {'args': ['-q'], 'paths': []}),  # Will run default test discovery
]

runner = Runner(steps, data=data)
PIPELINE = Pipeline([runner], data=data, runtime=runtime)
