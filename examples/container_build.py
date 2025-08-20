from gryt import Pipeline, Runner, SqliteData, LocalRuntime
from gryt import ContainerBuildStep

# Example: build a container image using the Docker SDK for Python.
# Requirements:
# - Docker daemon available (e.g., Docker Desktop, dockerd)
# - Python Docker SDK installed in your environment: pip install docker
# - A Dockerfile present in the specified context directory


data = SqliteData(in_memory=True)
runtime = LocalRuntime()

steps = [
    ContainerBuildStep(
        'build_image',
        config={
            'context_path': '.',
            'dockerfile': 'Dockerfile',
            'tags': ['gryt/example:latest'],
            'build_args': {},
            'pull': False,
            'push': False,
        },
        data=data,
    )
]

runner = Runner(steps, data=data)
PIPELINE = Pipeline([runner], data=data, runtime=runtime)
