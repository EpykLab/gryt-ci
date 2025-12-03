#!/usr/bin/env python3
"""
Simple example: Deploy to Fly.io after running tests

Usage:
    python examples/simple_flyio_deploy.py
"""
from gryt import (
    FlyDeployStep,
    LocalRuntime,
    Pipeline,
    PipInstallStep,
    PytestStep,
    Runner,
    SimpleVersioning,
    SqliteData,
    ToolValidator,
)

data = SqliteData(db_path='.gryt/gryt.db')
runtime = LocalRuntime()
version = SimpleVersioning().get_last_commit_hash()

validators = [
    ToolValidator(tools=[
        {"name": "python"},
        {"name": "pytest"},
        {"name": "fly"}
    ])
]

runner = Runner([
    # Install dependencies
    PipInstallStep('install_deps', {
        'requirements': 'requirements.txt'
    }, data=data),

    # Run tests
    PytestStep('run_tests', {
        'args': ['-v']
    }, data=data),

    # Deploy to Fly.io
    FlyDeployStep('deploy', {
        'app': 'my-app',
        'strategy': 'rolling',
        'build_arg': [f'VERSION={version}'],
        'auto_confirm': True
    }, data=data)
], data=data)

PIPELINE = Pipeline([runner], data=data, runtime=runtime, validators=validators)
