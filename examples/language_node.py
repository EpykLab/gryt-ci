from gryt import Pipeline, Runner, SqliteData, LocalRuntime
from gryt import NpmInstallStep, SvelteBuildStep

# Demonstrates Node/Svelte steps.
# Requires Node/npm installed. For SvelteBuildStep, a project with a package.json must exist in cwd.

data = SqliteData(in_memory=True)
runtime = LocalRuntime()

runner = Runner([
    NpmInstallStep('npm_install', {'cwd': '.', 'use_ci': True}),
    SvelteBuildStep('svelte_build', {'cwd': '.', 'script': 'build'}),
], data=data)

PIPELINE = Pipeline([runner], data=data, runtime=runtime)
