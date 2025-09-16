# Destinations

Destinations publish artifacts to remote services (registries, releases, etc.). They are designed to be explicit, lightweight, and customizable without heavy dependencies.

Key properties:
- Optional: A Pipeline can be given destinations and a list of artifacts to publish.
- Explicit: Publishes only when artifacts are provided to Pipeline.execute(artifacts=[...]).
- Robust: Returns per-artifact results and avoids raising for transient remote errors.

## API

Base class:

```python
from gryt import Destination

class Destination:
    def publish(self, artifacts):
        # artifacts is a list of file paths
        ...
```

Return value is a list of dicts like:
- artifact: str (path or logical id)
- status: 'success' | 'error'
- details: dict (optional)
- error: str (optional)

## Using Destinations with Pipeline

```python
from pathlib import Path
from gryt import Pipeline, Runner, CommandStep, SqliteData, LocalRuntime
from gryt import GitHubReleaseDestination

# Build steps create artifacts into ./dist or elsewhere
runner = Runner([
    CommandStep('build', {'cmd': ['bash', '-lc', 'mkdir -p dist && echo ok > dist/hello.txt']})
])

# Configure a destination (requires GITHUB_TOKEN in env)
dest = GitHubReleaseDestination(
    id='gh_release',
    config={
        'owner': 'your-org',
        'repo': 'your-repo',
        'tag': 'v0.1.0',
        'title': 'v0.1.0',
        'body': 'Automated release',
    },
)

PIPELINE = Pipeline([runner], runtime=LocalRuntime(), destinations=[dest])

# Later (CLI will call execute):
artifacts = [Path('dist/hello.txt')]
results = PIPELINE.execute(artifacts=artifacts)
print(results)
```

Notes:
- When destinations are present but `artifacts` is None/empty, no publish happens.
- Results from publish are merged into the pipeline result under `destinations`.

## Built-in Destinations

### CommandDestination
Runs a shell command for each artifact or once for all artifacts (templated placeholders).

Config:
- cmd: List[str] | str – base command. Placeholders {artifact}, {artifacts}
- per_artifact: bool (default True)
- cwd, env, timeout

Example (per artifact):
```python
from gryt import CommandDestination
cmd_dest = CommandDestination('scp_upload', {
    'cmd': 'scp {artifact} user@host:/uploads/',
    'per_artifact': True,
})
```

Example (single call):
```python
from gryt import CommandDestination
cmd_dest = CommandDestination('aws_s3_cp', {
    'cmd': 'aws s3 cp {artifacts} s3://my-bucket/releases/ --recursive',
    'per_artifact': False,
})
```

### NpmRegistryDestination
Publishes an npm package using `npm publish`.

Config:
- package_dir: str (default '.')
- registry: str (optional)
- tag: str (optional)
- access: str (optional)
- extra_args: List[str]
- env: dict (merged onto process env)

Auth:
- Set up `NPM_TOKEN` and .npmrc appropriately; or rely on your CI environment's npm auth.

Example:
```python
from gryt import NpmRegistryDestination
npm_dest = NpmRegistryDestination('npm_publish', {
    'package_dir': '.',
    'registry': 'https://registry.npmjs.org',
    'tag': 'latest',
})
```

For GitHub Packages registry (npm): set registry to `https://npm.pkg.github.com` and ensure scope in package.json and auth.

### PyPIDestination
Publishes Python distributions via `twine`. Requires `twine` available in the environment.

Config:
- dist_glob: str (default 'dist/*')
- repository_url: str (optional) – e.g., https://test.pypi.org/legacy/
- twine_exe: str (default 'python -m twine')
- extra_args: List[str]

Auth:
- `TWINE_USERNAME`/`TWINE_PASSWORD` or `TWINE_API_TOKEN`. See Twine docs.

Example:
```python
from gryt import PyPIDestination
pypi_dest = PyPIDestination('pypi', {
    'dist_glob': 'dist/*',
    'extra_args': ['--skip-existing'],
})
```

### ContainerRegistryDestination
Publishes arbitrary artifacts to any OCI-compliant container registry using the `oras` CLI (Docker Hub, GHCR, ECR, GCR, ACR, Harbor, etc.). Not limited to Docker registries or images.

Config:
- ref: str (required) – target OCI reference, e.g., ghcr.io/your-org/artifacts:v1
- tool: str (default 'oras') – currently only 'oras' is supported
- artifact_type: str (optional) – manifest artifact type, e.g., application/vnd.yourproj.bundle.v1+tar
- extra_args: List[str]
- env: dict (merged onto process env)
- cwd, timeout

Auth:
- Use `oras login <registry>` prior to publish, or rely on your CI's credential helpers.
- For AWS ECR, for example: `oras login -u AWS -p $(aws ecr get-login-password) <aws_account>.dkr.ecr.<region>.amazonaws.com`.

Example:
```python
from pathlib import Path
from gryt import Pipeline, Runner, CommandStep, LocalRuntime
from gryt import ContainerRegistryDestination

# Build step producing artifacts under ./dist
runner = Runner([
    CommandStep('build', {'cmd': ['bash', '-lc', 'mkdir -p dist && echo bin > dist/app-linux-amd64.tar.gz && echo bin > dist/app-darwin-arm64.tar.gz']})
])

oci_dest = ContainerRegistryDestination('oci_push', {
    'ref': 'ghcr.io/your-org/my-artifacts:v1',
    'artifact_type': 'application/vnd.yourproj.bundle.v1+tar',
})

PIPELINE = Pipeline([runner], runtime=LocalRuntime(), destinations=[oci_dest])
artifacts = [Path('dist/app-linux-amd64.tar.gz'), Path('dist/app-darwin-arm64.tar.gz')]
results = PIPELINE.execute(artifacts=artifacts)
print(results)
```

### GitHubReleaseDestination
Creates or finds a GitHub Release by tag and uploads files as assets via the GitHub REST API (no extra deps).

Config:
- owner, repo, tag (required)
- title, body, draft, prerelease (optional)
- overwrite_assets: bool (default True)

Auth:
- `GITHUB_TOKEN` env with repo scope.

Example:
```python
from gryt import GitHubReleaseDestination
release_dest = GitHubReleaseDestination('gh_rel', {
    'owner': 'your-org',
    'repo': 'your-repo',
    'tag': 'v0.1.0',
})
```

## Credentials and Security
- Prefer passing credentials via environment variables injected by your CI.
- Avoid printing tokens; built-in destinations do not log secrets.

## Patterns
- Use `CommandDestination` to integrate with ecosystems not yet covered (APT, AUR, custom registries) by calling appropriate CLIs.
- Consider combining with Hooks for observability (e.g., HttpHook to notify after publishing).
