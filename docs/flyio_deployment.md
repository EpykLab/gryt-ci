# Fly.io Deployment Step

The `FlyDeployStep` allows you to deploy applications to Fly.io as part of your gryt pipeline.

## Prerequisites

- [Fly.io CLI (`flyctl`)](https://fly.io/docs/hands-on/install-flyctl/) must be installed
- You must be authenticated with `fly auth login`
- Your application must have a `fly.toml` configuration file (or specify a custom config path)

## Basic Usage

```python
from gryt import FlyDeployStep, Runner, Pipeline, SqliteData, LocalRuntime

data = SqliteData(db_path='.gryt/gryt.db')
runtime = LocalRuntime()

runner = Runner([
    FlyDeployStep('deploy', {
        'app': 'my-app',
        'auto_confirm': True
    }, data=data)
], data=data)

PIPELINE = Pipeline([runner], data=data, runtime=runtime)
```

## Authentication

Authentication to Fly.io should be handled at the **Pipeline level** using the `auth_steps` parameter. This is especially useful in CI/CD or cloud environments where you cannot use `fly auth login` interactively.

### Using FlyAuth at Pipeline Level

```python
from gryt import FlyDeployStep, Runner, Pipeline, SqliteData, LocalRuntime
from gryt.auth import FlyAuth

data = SqliteData(db_path='.gryt/gryt.db')
runtime = LocalRuntime()

# Create auth instance
fly_auth = FlyAuth(
    id='fly_auth',
    config={'token_env_var': 'FLY_API_TOKEN'},  # Default
    data=data
)

# Create deploy step (no auth parameter)
deploy_step = FlyDeployStep(
    id='deploy',
    config={'app': 'my-app', 'auto_confirm': True},
    data=data
)

runner = Runner([deploy_step], data=data)

# Pass auth to pipeline
PIPELINE = Pipeline(
    runners=[runner],
    auth_steps=[fly_auth],  # Auth executes before runners
    data=data,
    runtime=runtime
)
```

### Setting the API Token

Before running your pipeline, set the `FLY_API_TOKEN` environment variable:

```bash
export FLY_API_TOKEN="your-fly-api-token-here"
```

You can obtain your API token from:
```bash
fly auth token
```

### Custom Token Environment Variable

You can use a different environment variable name:

```python
fly_auth = FlyAuth('fly_auth', {
    'token_env_var': 'MY_CUSTOM_FLY_TOKEN'
}, data=data)
```

### How It Works

1. Pipeline checks if `auth_steps` are provided
2. All auth steps execute sequentially **before** any runners start
3. The `FlyAuth.authenticate()` method reads the token from the environment variable
4. It authenticates to Fly.io using `fly auth token` command
5. Authentication is tracked in the database (if `data` is provided)
6. If authentication succeeds, the auth instance is marked as authenticated
7. If any auth step fails, pipeline execution stops immediately
8. Once all auth steps succeed, pipeline runners execute

### Local Development vs CI/CD

- **Local Development**: You can omit `auth_steps` if you're already logged in via `fly auth login`
- **CI/CD**: Use `FlyAuth` in `auth_steps` with the `FLY_API_TOKEN` environment variable for automated deployments

## Configuration Options

### Required

- None (if using default `fly.toml` in project root)

### Optional

#### Application Settings

- **app** (str): Fly.io app name. If not provided, uses app name from fly.toml
- **config** (str): Path to fly.toml config file (default: `fly.toml`)
- **region** (str): Target region for deployment (e.g., `iad`, `lax`, `fra`)

#### Deployment Strategy

- **strategy** (str): Deployment strategy
  - `rolling`: Deploy to instances one at a time (default)
  - `immediate`: Deploy to all instances immediately
  - `canary`: Deploy to a small number of instances first
  - `bluegreen`: Deploy to new instances, then switch traffic

#### Build Options

- **remote_only** (bool): Perform builds remotely on Fly.io (default: `false`)
- **no_cache** (bool): Do not use build cache (default: `false`)
- **dockerfile** (str): Path to Dockerfile if not in root
- **build_arg** (List[str]): Build arguments, e.g., `['VERSION=1.0.0', 'ENV=prod']`

#### Environment Variables

- **env** (Dict[str, str]): Environment variables to set during deployment

#### VM Configuration

- **vm_size** (str): VM size
  - `shared-cpu-1x`: Shared CPU, 1x size
  - `shared-cpu-2x`: Shared CPU, 2x size
  - `performance-1x`: Dedicated CPU, 1x size
  - `performance-2x`: Dedicated CPU, 2x size
  - And more (see [Fly.io docs](https://fly.io/docs/about/pricing/#machines))

#### High Availability

- **ha** (bool): Enable high availability (default: `false`)

#### Execution Options

- **auto_confirm** (bool): Skip confirmation prompts (default: `true`)
- **wait_timeout** (int): Seconds to wait for deployment to complete (default: `300`)
- **cwd** (str): Working directory
- **timeout** (float): Overall command timeout in seconds
- **retries** (int): Retry count on failure (default: `0`)

## Examples

### Basic Deployment

```python
from gryt import FlyDeployStep, Runner, Pipeline, SqliteData, LocalRuntime

data = SqliteData(db_path='.gryt/gryt.db')
runtime = LocalRuntime()

runner = Runner([
    FlyDeployStep('deploy', {
        'app': 'my-app',
        'auto_confirm': True
    }, data=data)
], data=data)

PIPELINE = Pipeline([runner], data=data, runtime=runtime)
```

### Production Deployment with Build Args

```python
from gryt import FlyDeployStep, Runner, Pipeline, SqliteData, LocalRuntime, SimpleVersioning

data = SqliteData(db_path='.gryt/gryt.db')
runtime = LocalRuntime()
version = SimpleVersioning().get_last_commit_hash()

runner = Runner([
    FlyDeployStep('deploy_production', {
        'app': 'my-production-app',
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

PIPELINE = Pipeline([runner], data=data, runtime=runtime)
```

### Remote Build with Custom Dockerfile

```python
runner = Runner([
    FlyDeployStep('deploy_remote', {
        'app': 'my-app',
        'remote_only': True,
        'dockerfile': 'Dockerfile.prod',
        'no_cache': True,
        'auto_confirm': True
    }, data=data)
], data=data)
```

### Canary Deployment

```python
runner = Runner([
    FlyDeployStep('deploy_canary', {
        'app': 'my-app',
        'strategy': 'canary',
        'wait_timeout': 900,
        'auto_confirm': True
    }, data=data)
], data=data)
```

## Deploying Pre-Built Docker Images

Instead of building from source, you can deploy pre-built Docker images. This is useful when:
- You've already built and tested an image in your CI/CD pipeline
- You want to deploy the exact same image to multiple environments
- You're using a separate build system

### Deploy from Docker Registry

```python
FlyDeployStep('deploy', {
    'app': 'my-app',
    'image': 'myregistry.io/myapp:v1.2.3',  # Pre-built image
    'auto_confirm': True
}, data=data)
```

### Deploy Local Docker Image

If you've built an image locally:

```bash
# Build your image first
docker build -t my-local-app:v1.0.0 .
```

Then deploy it:

```python
FlyDeployStep('deploy', {
    'app': 'my-app',
    'image': 'my-local-app:v1.0.0',  # Local image
    'auto_confirm': True
}, data=data)
```

### Deploy from Docker Hub

```python
FlyDeployStep('deploy', {
    'app': 'my-app',
    'image': 'username/myapp:latest',  # Docker Hub image
    'strategy': 'rolling',
    'auto_confirm': True
}, data=data)
```

### Deploy with Version Tag

```python
from gryt import SimpleVersioning

version = SimpleVersioning().get_last_commit_hash()
image_name = f'myregistry.io/myapp:{version}'

FlyDeployStep('deploy', {
    'app': 'my-app',
    'image': image_name,
    'strategy': 'rolling',
    'ha': True,
    'auto_confirm': True
}, data=data)
```

**Note:** When using the `image` parameter, build-related options (`dockerfile`, `build_arg`, `no_cache`, `remote_only`) are ignored since no build is performed.

## Integration with CI/CD

The FlyDeployStep can be integrated into your gryt pipeline for automated deployments:

```python
#!/usr/bin/env python3
from gryt import (
    FlyDeployStep,
    PipInstallStep,
    PytestStep,
    Runner,
    Pipeline,
    SqliteData,
    LocalRuntime,
    SimpleVersioning,
    ToolValidator,
)
from gryt.auth import FlyAuth

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

# Create auth step for CI/CD
fly_auth = FlyAuth(
    id='fly_auth',
    config={'token_env_var': 'FLY_API_TOKEN'},
    data=data
)

runner = Runner([
    PipInstallStep('install_deps', {
        'requirements': 'requirements.txt'
    }, data=data),

    PytestStep('run_tests', {
        'args': ['-v']
    }, data=data),

    FlyDeployStep('deploy', {
        'app': 'my-app',
        'strategy': 'rolling',
        'build_arg': [f'VERSION={version}'],
        'auto_confirm': True
    }, data=data)
], data=data)

PIPELINE = Pipeline(
    runners=[runner],
    auth_steps=[fly_auth],  # Auth runs before all steps
    data=data,
    runtime=runtime,
    validators=validators
)
```

## Troubleshooting

### Authentication Issues

**Local Development:**
If you encounter authentication errors, ensure you're logged in:

```bash
fly auth login
```

**CI/CD:**
Ensure the `FLY_API_TOKEN` environment variable is set and contains a valid token:

```bash
export FLY_API_TOKEN="your-token-here"
```

Get your token with:
```bash
fly auth token
```

If authentication fails in the pipeline, check the auth step output in the database for details.

### Build Failures

If builds fail, try:
1. Using `no_cache: true` to force a fresh build
2. Using `remote_only: true` to build on Fly.io's infrastructure
3. Checking your Dockerfile for issues

### Timeout Issues

If deployments time out:
1. Increase `wait_timeout` (default is 300 seconds)
2. Check Fly.io's status page for any platform issues
3. Review your application's health check configuration

## Additional Resources

- [Fly.io Documentation](https://fly.io/docs/)
- [Fly.io CLI Reference](https://fly.io/docs/flyctl/)
- [Fly.io Deployment Strategies](https://fly.io/docs/reference/configuration/#deploy-section)
