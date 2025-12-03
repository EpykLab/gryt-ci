#!/usr/bin/env python3
"""Example pipeline for deploying to Fly.io"""
from gryt import (
    FlyAuth,
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

# Example 1: Basic deployment
def basic_deployment():
    validators = [
        ToolValidator(tools=[{"name": "fly"}])
    ]

    runner = Runner([
        FlyDeployStep('deploy', {
            'app': 'my-app',
            'auto_confirm': True
        })
    ], data=data)

    return Pipeline([runner], data=data, runtime=runtime, validators=validators)


# Example 2: Full CI/CD pipeline with tests and deployment
def cicd_pipeline():
    validators = [
        ToolValidator(tools=[
            {"name": "python"},
            {"name": "pytest"},
            {"name": "fly"}
        ])
    ]

    runner = Runner([
        PipInstallStep('install_deps', {
            'requirements': 'requirements.txt'
        }, data=data),

        PytestStep('run_tests', {
            'args': ['-v', '--maxfail=1']
        }, data=data),

        FlyDeployStep('deploy', {
            'app': 'my-app',
            'strategy': 'rolling',
            'auto_confirm': True
        }, data=data)
    ], data=data)

    return Pipeline([runner], data=data, runtime=runtime, validators=validators)


# Example 3: Production deployment with build args and environment variables
def production_deployment():
    validators = [
        ToolValidator(tools=[{"name": "fly"}])
    ]

    runner = Runner([
        FlyDeployStep('deploy_production', {
            'app': 'my-production-app',
            'config': 'fly.production.toml',
            'strategy': 'rolling',
            'build_arg': [
                f'VERSION={version}',
                'ENV=production',
            ],
            'env': {
                'DATABASE_URL': 'postgres://prod.example.com/db',
                'API_KEY': 'production-secret',
            },
            'region': 'iad',
            'vm_size': 'performance-2x',
            'ha': True,
            'wait_timeout': 600,
            'auto_confirm': True,
            'retries': 2
        }, data=data)
    ], data=data)

    return Pipeline([runner], data=data, runtime=runtime, validators=validators)


# Example 4: Remote build with custom Dockerfile
def remote_build_deployment():
    validators = [
        ToolValidator(tools=[{"name": "fly"}])
    ]

    runner = Runner([
        FlyDeployStep('deploy_remote', {
            'app': 'my-app',
            'remote_only': True,
            'dockerfile': 'Dockerfile.prod',
            'no_cache': True,
            'auto_confirm': True
        }, data=data)
    ], data=data)

    return Pipeline([runner], data=data, runtime=runtime, validators=validators)


# Example 5: Canary deployment
def canary_deployment():
    validators = [
        ToolValidator(tools=[{"name": "fly"}])
    ]

    runner = Runner([
        FlyDeployStep('deploy_canary', {
            'app': 'my-app',
            'strategy': 'canary',
            'wait_timeout': 900,
            'auto_confirm': True
        }, data=data)
    ], data=data)

    return Pipeline([runner], data=data, runtime=runtime, validators=validators)


# Example 6: Deployment with authentication (for CI/cloud environments)
def authenticated_deployment():
    """
    Use this in CI/CD or cloud environments where you need to authenticate
    using a FLY_API_TOKEN environment variable.

    Set the environment variable before running:
        export FLY_API_TOKEN="your-token-here"
    """
    validators = [
        ToolValidator(tools=[{"name": "fly"}])
    ]

    # Create auth instance that will authenticate using FLY_API_TOKEN env var
    fly_auth = FlyAuth('fly_auth', {
        'token_env_var': 'FLY_API_TOKEN'  # This is the default
    }, data=data)

    runner = Runner([
        FlyDeployStep('deploy', {
            'app': 'my-app',
            'strategy': 'rolling',
            'build_arg': [f'VERSION={version}'],
            'auto_confirm': True
        }, data=data, auth=fly_auth)  # Pass auth to the deploy step
    ], data=data)

    return Pipeline([runner], data=data, runtime=runtime, validators=validators)


# Default pipeline (use the CI/CD pipeline)
PIPELINE = cicd_pipeline()
