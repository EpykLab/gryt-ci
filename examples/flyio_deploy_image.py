#!/usr/bin/env python3
"""Example: Deploy pre-built Docker images to Fly.io"""
from gryt import (
    FlyAuth,
    FlyDeployStep,
    LocalRuntime,
    Pipeline,
    Runner,
    SimpleVersioning,
    SqliteData,
    ToolValidator,
)

data = SqliteData(db_path='.gryt/gryt.db')
runtime = LocalRuntime()
version = SimpleVersioning().get_last_commit_hash()

# Example 1: Deploy from Docker Hub
def deploy_from_dockerhub():
    """Deploy a public image from Docker Hub"""
    validators = [
        ToolValidator(tools=[{"name": "fly"}])
    ]

    runner = Runner([
        FlyDeployStep('deploy', {
            'app': 'my-app',
            'image': 'myusername/myapp:latest',  # Docker Hub image
            'auto_confirm': True
        }, data=data)
    ], data=data)

    return Pipeline([runner], data=data, runtime=runtime, validators=validators)


# Example 2: Deploy from private registry
def deploy_from_private_registry():
    """Deploy from a private container registry (e.g., AWS ECR, GCR, etc.)"""
    validators = [
        ToolValidator(tools=[{"name": "fly"}])
    ]

    runner = Runner([
        FlyDeployStep('deploy', {
            'app': 'my-app',
            'image': 'myregistry.io/mycompany/myapp:v1.2.3',  # Private registry
            'strategy': 'rolling',
            'auto_confirm': True
        }, data=data)
    ], data=data)

    return Pipeline([runner], data=data, runtime=runtime, validators=validators)


# Example 3: Deploy local Docker image
def deploy_local_image():
    """Deploy a Docker image built locally

    First build your image locally:
        docker build -t my-local-app:v1.0.0 .

    Then deploy it to Fly.io using this pipeline
    """
    validators = [
        ToolValidator(tools=[{"name": "fly"}])
    ]

    runner = Runner([
        FlyDeployStep('deploy', {
            'app': 'my-app',
            'image': 'my-local-app:v1.0.0',  # Local image
            'auto_confirm': True
        }, data=data)
    ], data=data)

    return Pipeline([runner], data=data, runtime=runtime, validators=validators)


# Example 4: Deploy with version tag from git
def deploy_versioned_image():
    """Deploy an image tagged with the current git commit hash"""
    validators = [
        ToolValidator(tools=[{"name": "fly"}])
    ]

    # Assume you've already built and tagged the image with the version
    image_name = f'myregistry.io/myapp:{version}'

    runner = Runner([
        FlyDeployStep('deploy', {
            'app': 'my-app',
            'image': image_name,
            'strategy': 'rolling',
            'ha': True,
            'auto_confirm': True
        }, data=data)
    ], data=data)

    return Pipeline([runner], data=data, runtime=runtime, validators=validators)


# Example 5: Build, push, and deploy with authentication
def build_push_deploy_pipeline():
    """Complete pipeline: build image, push to registry, deploy to Fly.io

    This demonstrates a full CI/CD workflow with authentication
    """
    validators = [
        ToolValidator(tools=[{"name": "docker"}, {"name": "fly"}])
    ]

    image_name = f'myregistry.io/myapp:{version}'

    # Create auth for Fly.io
    fly_auth = FlyAuth('fly_auth', {
        'token_env_var': 'FLY_API_TOKEN'
    }, data=data)

    # Note: You would typically add ContainerBuildStep here to build the image
    # For this example, we assume the image is already built and pushed

    runner = Runner([
        FlyDeployStep('deploy', {
            'app': 'my-production-app',
            'image': image_name,
            'strategy': 'rolling',
            'region': 'iad',
            'vm_size': 'performance-2x',
            'ha': True,
            'wait_timeout': 600,
            'auto_confirm': True
        }, data=data, auth=fly_auth)
    ], data=data)

    return Pipeline([runner], data=data, runtime=runtime, validators=validators)


# Example 6: Multi-stage deployment (staging then production)
def multi_stage_deployment():
    """Deploy the same image to staging, then production"""
    validators = [
        ToolValidator(tools=[{"name": "fly"}])
    ]

    image_name = f'myregistry.io/myapp:{version}'

    # Deploy to staging first
    staging_runner = Runner([
        FlyDeployStep('deploy_staging', {
            'app': 'my-app-staging',
            'image': image_name,
            'strategy': 'immediate',  # Fast deployment for staging
            'auto_confirm': True
        }, data=data)
    ], data=data)

    # Then deploy to production
    production_runner = Runner([
        FlyDeployStep('deploy_production', {
            'app': 'my-app-production',
            'image': image_name,
            'strategy': 'rolling',  # Careful rolling deployment for production
            'ha': True,
            'wait_timeout': 900,
            'auto_confirm': True
        }, data=data)
    ], data=data)

    return Pipeline([staging_runner, production_runner], data=data, runtime=runtime, validators=validators)


# Default pipeline
PIPELINE = deploy_local_image()
