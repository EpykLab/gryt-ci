# Authentication

Authentication in gryt is handled at the **Pipeline level** using Auth instances. This allows you to authenticate to external services before any pipeline runners execute.

---

## Overview

### Key Concepts

- **Auth**: Abstract base class for authentication mechanisms
- **auth_steps**: Pipeline parameter that accepts a list of Auth instances
- **Sequential Execution**: All auth steps execute in order before any runners
- **Fail-Fast**: If any auth step fails, pipeline execution stops immediately
- **Database Tracking**: Auth results are logged to the database (if Data is provided)

### Execution Flow

```
Pipeline.execute()
  ↓
1. Run environment validators (if any)
  ↓
2. Execute all auth_steps sequentially
  ↓
3. If any auth fails → return error, stop pipeline
  ↓
4. If all auth succeeds → execute runners
  ↓
5. Execute runtime provisioning
  ↓
6. Run all runners (sequential or parallel)
```

---

## Basic Usage

```python
from gryt import Pipeline, Runner, CommandStep
from gryt.auth import FlyAuth, DockerRegistryAuth

# Create auth instances
fly_auth = FlyAuth(
    id="fly-auth",
    config={"token_env_var": "FLY_API_TOKEN"}
)

ghcr_auth = DockerRegistryAuth(
    id="ghcr-auth",
    config={
        "registry": "ghcr.io",
        "username_env_var": "GITHUB_USERNAME",
        "token_env_var": "GITHUB_TOKEN"
    }
)

# Create pipeline with auth steps
pipeline = Pipeline(
    runners=[Runner(steps=[...])],
    auth_steps=[ghcr_auth, fly_auth]  # Execute before runners
)

# Execute pipeline (auth runs automatically)
pipeline.execute()
```

---

## Built-in Auth Types

### FlyAuth

Authenticate to Fly.io using an API token.

#### Configuration

```python
from gryt.auth import FlyAuth

fly_auth = FlyAuth(
    id="fly-auth",
    config={
        "token_env_var": "FLY_API_TOKEN",  # Default
        "timeout": 30  # Optional timeout in seconds
    },
    data=data  # Optional Data instance for tracking
)
```

#### Environment Variables

```bash
# Get your Fly.io API token
fly auth token

# Set it as an environment variable
export FLY_API_TOKEN="your-token-here"
```

#### How It Works

1. Reads API token from environment variable (`FLY_API_TOKEN` by default)
2. Executes `fly auth token` command with token piped to stdin
3. Marks authentication as successful if command succeeds
4. Logs result to database (if Data is provided)

#### Example

```python
from gryt import Pipeline, Runner, FlyDeployStep, SqliteData
from gryt.auth import FlyAuth

data = SqliteData(db_path='.gryt/gryt.db')

fly_auth = FlyAuth(
    id="fly-auth",
    config={"token_env_var": "FLY_API_TOKEN"},
    data=data
)

deploy_step = FlyDeployStep(
    id="deploy",
    config={"app": "my-app", "auto_confirm": True},
    data=data
)

pipeline = Pipeline(
    runners=[Runner(steps=[deploy_step])],
    auth_steps=[fly_auth],
    data=data
)
```

---

### DockerRegistryAuth

Authenticate to Docker container registries (GitHub Container Registry, Docker Hub, GitLab, etc.).

#### Configuration

```python
from gryt.auth import DockerRegistryAuth

docker_auth = DockerRegistryAuth(
    id="registry-auth",
    config={
        "registry": "ghcr.io",  # Default: "docker.io"
        "username_env_var": "DOCKER_USERNAME",  # Default
        "token_env_var": "DOCKER_TOKEN",  # Default
        "timeout": 30  # Optional timeout in seconds
    },
    data=data  # Optional Data instance for tracking
)
```

#### Supported Registries

- **GitHub Container Registry**: `ghcr.io`
- **Docker Hub**: `docker.io` (default)
- **GitLab Container Registry**: `registry.gitlab.com`
- **AWS ECR**: `<account-id>.dkr.ecr.<region>.amazonaws.com`
- **Google Container Registry**: `gcr.io`, `us.gcr.io`, `eu.gcr.io`, etc.
- **Azure Container Registry**: `<registry-name>.azurecr.io`
- Any other Docker-compatible registry

#### Environment Variables

```bash
# GitHub Container Registry
export DOCKER_USERNAME="your-github-username"
export DOCKER_TOKEN="ghp_xxxxxxxxxxxx"

# Docker Hub
export DOCKER_USERNAME="your-dockerhub-username"
export DOCKER_TOKEN="dckr_pat_xxxxxxxxxxxx"

# GitLab
export DOCKER_USERNAME="your-gitlab-username"
export DOCKER_TOKEN="glpat-xxxxxxxxxxxx"
```

#### How It Works

1. Reads username and token from environment variables
2. Executes `docker login <registry> --username <username> --password-stdin`
3. Pipes token to stdin for secure authentication
4. Marks authentication as successful if login succeeds
5. Logs result to database (if Data is provided)

#### Examples

##### GitHub Container Registry

```python
from gryt.auth import DockerRegistryAuth

ghcr_auth = DockerRegistryAuth(
    id="ghcr",
    config={
        "registry": "ghcr.io",
        "username_env_var": "GITHUB_USERNAME",
        "token_env_var": "GITHUB_TOKEN"
    }
)
```

##### Docker Hub

```python
dockerhub_auth = DockerRegistryAuth(
    id="dockerhub",
    config={
        "registry": "docker.io",  # or omit (docker.io is default)
        "username_env_var": "DOCKER_USERNAME",
        "token_env_var": "DOCKER_TOKEN"
    }
)
```

##### GitLab Container Registry

```python
gitlab_auth = DockerRegistryAuth(
    id="gitlab",
    config={
        "registry": "registry.gitlab.com",
        "username_env_var": "GITLAB_USERNAME",
        "token_env_var": "GITLAB_TOKEN"
    }
)
```

---

## Common Patterns

### Multiple Registries

Authenticate to multiple container registries in a single pipeline:

```python
from gryt import Pipeline, Runner, CommandStep
from gryt.auth import DockerRegistryAuth

# Authenticate to multiple registries
ghcr_auth = DockerRegistryAuth(id="ghcr", config={"registry": "ghcr.io"})
dockerhub_auth = DockerRegistryAuth(id="dockerhub", config={"registry": "docker.io"})

# Build and push to both registries
build_step = CommandStep(
    id="build",
    config={"cmd": ["docker", "build", "-t", "myapp:latest", "."]}
)

tag_and_push_ghcr = CommandStep(
    id="push-ghcr",
    config={"cmd": [
        "docker", "tag", "myapp:latest", "ghcr.io/user/myapp:latest", "&&",
        "docker", "push", "ghcr.io/user/myapp:latest"
    ]}
)

tag_and_push_dockerhub = CommandStep(
    id="push-dockerhub",
    config={"cmd": [
        "docker", "tag", "myapp:latest", "user/myapp:latest", "&&",
        "docker", "push", "user/myapp:latest"
    ]}
)

pipeline = Pipeline(
    runners=[Runner(steps=[build_step, tag_and_push_ghcr, tag_and_push_dockerhub])],
    auth_steps=[ghcr_auth, dockerhub_auth]  # Both authenticate before any steps
)
```

### CI/CD Pipeline

Complete CI/CD pipeline with authentication:

```python
#!/usr/bin/env python3
from gryt import Pipeline, Runner, CommandStep, SqliteData, LocalRuntime
from gryt.auth import DockerRegistryAuth, FlyAuth
import os

# Get version from environment or git
version = os.getenv("VERSION", "latest")

data = SqliteData(db_path='.gryt/gryt.db')
runtime = LocalRuntime()

# Auth steps
ghcr_auth = DockerRegistryAuth(
    id="ghcr",
    config={"registry": "ghcr.io"},
    data=data
)

fly_auth = FlyAuth(
    id="fly",
    config={"token_env_var": "FLY_API_TOKEN"},
    data=data
)

# Build and deploy steps
runner = Runner([
    # Build Docker image
    CommandStep(
        id="build",
        config={"cmd": ["docker", "build", "-t", f"ghcr.io/user/app:{version}", "."]}
    ),

    # Push to registry
    CommandStep(
        id="push",
        config={"cmd": ["docker", "push", f"ghcr.io/user/app:{version}"]}
    ),

    # Deploy to Fly.io
    FlyDeployStep(
        id="deploy",
        config={
            "app": "my-app",
            "image": f"ghcr.io/user/app:{version}",
            "strategy": "rolling",
            "auto_confirm": True
        }
    )
], data=data)

PIPELINE = Pipeline(
    runners=[runner],
    auth_steps=[ghcr_auth, fly_auth],  # Authenticate to both services
    data=data,
    runtime=runtime
)

if __name__ == "__main__":
    result = PIPELINE.execute()
    print(f"Pipeline result: {result}")
```

### Conditional Authentication

Only authenticate in CI/CD environments:

```python
import os
from gryt import Pipeline, Runner
from gryt.auth import FlyAuth

# Only add auth if in CI/CD (FLY_API_TOKEN is set)
auth_steps = []
if os.getenv("FLY_API_TOKEN"):
    auth_steps.append(FlyAuth(id="fly", config={"token_env_var": "FLY_API_TOKEN"}))

pipeline = Pipeline(
    runners=[...],
    auth_steps=auth_steps  # Empty in local dev, contains FlyAuth in CI/CD
)
```

---

## Custom Auth Implementation

You can create custom Auth implementations by extending the `Auth` base class:

```python
from gryt.auth import Auth
import subprocess
from typing import Dict, Any

class MyCustomAuth(Auth):
    """Authenticate to a custom service."""

    def authenticate(self) -> Dict[str, Any]:
        """Perform authentication and return result."""
        # Check if already authenticated
        if self._authenticated:
            return {
                "status": "success",
                "message": "Already authenticated",
                "skipped": True
            }

        # Get credentials from config
        api_key = os.environ.get(self.config.get("api_key_env_var", "API_KEY"))
        timeout = self.config.get("timeout")

        if not api_key:
            error_msg = "API key not found in environment"
            result = {
                "status": "error",
                "error": error_msg
            }
            if self.data:
                self.data.insert("auth_output", {
                    "auth_id": self.id,
                    "type": "MyCustomAuth",
                    "output_json": result,
                    "status": "error",
                })
            return result

        # Perform authentication
        try:
            proc = subprocess.Popen(
                ["my-cli", "auth", "login"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            stdout, stderr = proc.communicate(input=api_key, timeout=timeout)

            if proc.returncode == 0:
                self._authenticated = True
                result = {
                    "status": "success",
                    "message": "Successfully authenticated",
                    "stdout": stdout.strip()
                }
                if self.data:
                    self.data.insert("auth_output", {
                        "auth_id": self.id,
                        "type": "MyCustomAuth",
                        "output_json": result,
                        "status": "success",
                    })
                return result
            else:
                error_msg = f"Authentication failed: {stderr}"
                result = {
                    "status": "error",
                    "error": error_msg,
                    "returncode": proc.returncode
                }
                if self.data:
                    self.data.insert("auth_output", {
                        "auth_id": self.id,
                        "type": "MyCustomAuth",
                        "output_json": result,
                        "status": "error",
                    })
                return result

        except subprocess.TimeoutExpired:
            error_msg = "Authentication timed out"
            result = {"status": "error", "error": error_msg}
            if self.data:
                self.data.insert("auth_output", {
                    "auth_id": self.id,
                    "type": "MyCustomAuth",
                    "output_json": result,
                    "status": "error",
                })
            return result
        except Exception as e:
            error_msg = f"Authentication error: {str(e)}"
            result = {"status": "error", "error": error_msg}
            if self.data:
                self.data.insert("auth_output", {
                    "auth_id": self.id,
                    "type": "MyCustomAuth",
                    "output_json": result,
                    "status": "error",
                })
            return result
```

### Usage

```python
custom_auth = MyCustomAuth(
    id="custom",
    config={"api_key_env_var": "MY_API_KEY", "timeout": 30},
    data=data
)

pipeline = Pipeline(
    runners=[...],
    auth_steps=[custom_auth]
)
```

---

## Troubleshooting

### Authentication Fails in Pipeline

**Check environment variables:**
```bash
# Verify variables are set
echo $FLY_API_TOKEN
echo $DOCKER_USERNAME
echo $DOCKER_TOKEN
```

**Check auth output in database:**
```python
from gryt import SqliteData

data = SqliteData(db_path='.gryt/gryt.db')
results = data.query("SELECT * FROM auth_output ORDER BY timestamp DESC LIMIT 10")
for row in results:
    print(row)
```

### Docker Login Fails

**Verify Docker is running:**
```bash
docker ps
```

**Test manual login:**
```bash
echo $DOCKER_TOKEN | docker login ghcr.io --username $DOCKER_USERNAME --password-stdin
```

### Fly.io Authentication Fails

**Verify token is valid:**
```bash
fly auth token
```

**Test manual authentication:**
```bash
echo $FLY_API_TOKEN | fly auth token
```

### Timeout Issues

Increase timeout in auth config:
```python
auth = DockerRegistryAuth(
    id="registry",
    config={
        "registry": "ghcr.io",
        "timeout": 60  # Increase from default 30
    }
)
```

---

## Migration Guide

### From Step-Level Auth (Deprecated)

**Old approach:**
```python
# ❌ Don't do this (deprecated)
from gryt.auth import FlyAuth

fly_auth = FlyAuth(id="fly", config={"token_env_var": "FLY_API_TOKEN"})

deploy_step = FlyDeployStep(
    id="deploy",
    config={"app": "my-app"},
    auth=fly_auth  # ❌ auth parameter is deprecated
)

runner = Runner(steps=[deploy_step])
pipeline = Pipeline(runners=[runner])
```

**New approach:**
```python
# ✅ Do this instead (recommended)
from gryt.auth import FlyAuth

fly_auth = FlyAuth(id="fly", config={"token_env_var": "FLY_API_TOKEN"})

deploy_step = FlyDeployStep(
    id="deploy",
    config={"app": "my-app"}
    # No auth parameter
)

runner = Runner(steps=[deploy_step])
pipeline = Pipeline(
    runners=[runner],
    auth_steps=[fly_auth]  # ✅ Auth at pipeline level
)
```

### Benefits of Pipeline-Level Auth

1. **Centralized**: All authentication happens in one place
2. **Reusable**: Same auth can be used across multiple steps
3. **Fail-Fast**: Pipeline stops immediately if auth fails
4. **Separation of Concerns**: Steps focus on their task, not authentication
5. **Multiple Services**: Easily authenticate to multiple services

---

## Best Practices

### 1. Use Environment Variables for Secrets

```python
# ✅ Good: Use environment variables
fly_auth = FlyAuth(
    id="fly",
    config={"token_env_var": "FLY_API_TOKEN"}
)

# ❌ Bad: Hardcode secrets
fly_auth = FlyAuth(
    id="fly",
    config={"token": "hardcoded-secret"}  # Don't do this!
)
```

### 2. Order Auth Steps Appropriately

Put auth steps in the order they're needed:
```python
pipeline = Pipeline(
    runners=[...],
    auth_steps=[
        DockerRegistryAuth(...),  # First, auth to registry
        FlyAuth(...)              # Then, auth to Fly.io
    ]
)
```

### 3. Track Auth Results

Always provide a Data instance to track auth results:
```python
data = SqliteData(db_path='.gryt/gryt.db')

auth = FlyAuth(
    id="fly",
    config={"token_env_var": "FLY_API_TOKEN"},
    data=data  # ✅ Track auth results
)
```

### 4. Use Descriptive IDs

```python
# ✅ Good: Descriptive ID
ghcr_auth = DockerRegistryAuth(id="ghcr-production", config={...})

# ❌ Bad: Generic ID
auth = DockerRegistryAuth(id="auth1", config={...})
```

### 5. Handle CI/CD vs Local Development

```python
import os

# Different auth strategies for different environments
if os.getenv("CI"):
    # CI/CD: Use token-based auth
    auth_steps = [
        FlyAuth(id="fly", config={"token_env_var": "FLY_API_TOKEN"})
    ]
else:
    # Local: Assume already logged in
    auth_steps = []

pipeline = Pipeline(runners=[...], auth_steps=auth_steps)
```

---

## Additional Resources

- [Pipeline Documentation](PIPELINES.md#authentication)
- [Fly.io Deployment](flyio_deployment.md#authentication)
- [Concepts](concepts.md#auth)
