#!/usr/bin/env python3
from gryt import ContainerBuildStep, GoBuildStep, GoModDownloadStep, GoTestStep, LocalRuntime, Pipeline, Runner, SqliteData

# Workflow created by `gryt new`

# Use project-local database by default
# Tip: if you prefer ephemeral runs during experimentation, use SqliteData(in_memory=True)

data = SqliteData(db_path='.gryt/gryt.db')
runtime = LocalRuntime()

runner = Runner([
    GoModDownloadStep('go_mod_download', {'cwd': '.'}, data=data),
    GoBuildStep('go_build', {'cwd': '.', 'packages': ['./...']}, data=data),
    GoTestStep('go_test', {'cwd': '.', 'packages': ['./...'], 'json': False}, data=data),
    ContainerBuildStep('build_image', {'context_path': '.', 'dockerfile': 'Dockerfile', 'tags': [], 'pull': False, 'push': False}, data=data),
], data=data)

PIPELINE = Pipeline([runner], data=data, runtime=runtime)
