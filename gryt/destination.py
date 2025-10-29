from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

PathLike = Union[str, Path]


class Destination(ABC):
    """Abstract destination that can publish one or more artifacts.

    Design goals:
    - Simple, explicit API: publish(artifacts) -> List[Dict[str, Any]].
    - Customizable via config dict; minimal assumptions.
    - Robust by default: subclasses should raise exceptions only for
      misconfiguration; network/remote errors should be reported in results.
    - No heavy dependencies; rely on stdlib or common CLIs (npm, twine, git).
    """

    def __init__(self, id: str, config: Optional[Dict[str, Any]] = None, hook: Optional["Hook"] = None) -> None:
        self.id = id
        self.config = config or {}
        self.hook = hook

    @abstractmethod
    def publish(self, artifacts: Sequence[PathLike]) -> List[Dict[str, Any]]:
        """Publish given artifacts.

        Returns a list of per-artifact results dicts with keys like:
        - artifact: str (path)
        - status: 'success' | 'error'
        - details: dict (optional)
        - error: str (optional)
        """

    # Helper utilities for subclasses
    def _as_paths(self, artifacts: Sequence[PathLike]) -> List[Path]:
        return [Path(a) for a in artifacts]


class CommandDestination(Destination):
    """Run a shell command for each artifact or once for all artifacts.

    Config:
    - cmd: List[str] | str – base command. Supports placeholders:
      - {artifact}: current artifact path
      - {artifacts}: space-joined list of all artifacts
    - per_artifact: bool (default True) – if True, run once per artifact;
      if False, run once with all artifacts substituted into {artifacts}.
    - cwd, env (dict), timeout (float)
    """

    def publish(self, artifacts: Sequence[PathLike]) -> List[Dict[str, Any]]:
        import shlex

        cfg = self.config
        per_artifact = bool(cfg.get("per_artifact", True))
        cwd = cfg.get("cwd")
        env = cfg.get("env")
        timeout = cfg.get("timeout")
        base_cmd = cfg.get("cmd")
        if not base_cmd:
            raise ValueError("CommandDestination requires config['cmd']")

        results: List[Dict[str, Any]] = []
        paths = self._as_paths(artifacts)
        artifacts_str = " ".join(shlex.quote(str(p)) for p in paths)

        def run_cmd(cmd_str_or_list: Union[str, List[str]]) -> Tuple[int, str, str]:
            if isinstance(cmd_str_or_list, str):
                # Use shell to expand placeholders safely already quoted
                completed = subprocess.run(cmd_str_or_list, shell=True, capture_output=True, text=True, cwd=cwd, env=env, timeout=timeout)
            else:
                completed = subprocess.run(cmd_str_or_list, capture_output=True, text=True, cwd=cwd, env=env, timeout=timeout)
            return completed.returncode, completed.stdout, completed.stderr

        if per_artifact:
            for p in paths:
                if isinstance(base_cmd, str):
                    cmd = base_cmd.format(artifact=shlex.quote(str(p)), artifacts=artifacts_str)
                else:
                    cmd = [c.format(artifact=str(p), artifacts=" ".join(str(x) for x in paths)) for c in base_cmd]
                code, out, err = run_cmd(cmd)
                results.append({
                    "artifact": str(p),
                    "status": "success" if code == 0 else "error",
                    "details": {"stdout": out, "stderr": err, "returncode": code},
                })
        else:
            if isinstance(base_cmd, str):
                cmd = base_cmd.format(artifact="", artifacts=artifacts_str)
            else:
                cmd = [c.format(artifact="", artifacts=" ".join(str(x) for x in paths)) for c in base_cmd]
            code, out, err = run_cmd(cmd)
            status = "success" if code == 0 else "error"
            for p in paths:
                results.append({
                    "artifact": str(p),
                    "status": status,
                    "details": {"stdout": out, "stderr": err, "returncode": code},
                })
        return results


class NpmRegistryDestination(Destination):
    """Publish to an npm-compatible registry via `npm publish`.

    Config:
    - package_dir: str (default '.') – directory containing package.json
    - registry: str (optional) – e.g., https://registry.npmjs.org or https://npm.pkg.github.com
    - tag: str (optional) – npm dist-tag (e.g., 'latest', 'beta')
    - access: str (optional) – 'public' or 'restricted'
    - extra_args: List[str] – additional flags
    - env: dict – additional environment variables

    Auth:
    - Typically via env NPM_TOKEN with an .npmrc using //registry/:_authToken=${NPM_TOKEN}
      You can also pass registry-specific env via config['env'].
    """

    def publish(self, artifacts: Sequence[PathLike]) -> List[Dict[str, Any]]:
        # npm publish doesn't take artifact files; it publishes the package_dir.
        # We will ignore artifacts and publish once for package_dir.
        cfg = self.config
        pkg_dir = cfg.get("package_dir", ".")
        registry = cfg.get("registry")
        tag = cfg.get("tag")
        access = cfg.get("access")
        extra = cfg.get("extra_args") or []
        env = os.environ.copy()
        env.update(cfg.get("env", {}))
        cmd: List[str] = ["npm", "publish"]
        if registry:
            cmd += ["--registry", registry]
        if tag:
            cmd += ["--tag", tag]
        if access:
            cmd += ["--access", access]
        cmd += list(extra)
        try:
            cp = subprocess.run(cmd, cwd=pkg_dir, capture_output=True, text=True, env=env, check=False)
            return [{
                "artifact": pkg_dir,
                "status": "success" if cp.returncode == 0 else "error",
                "details": {"stdout": cp.stdout, "stderr": cp.stderr, "returncode": cp.returncode},
            }]
        except Exception as e:  # noqa: BLE001
            return [{"artifact": pkg_dir, "status": "error", "error": str(e)}]


class PyPIDestination(Destination):
    """Publish Python distributions to PyPI (or custom repo) via twine.

    Config:
    - dist_glob: str (default 'dist/*') – files to upload
    - repository_url: str (optional) – custom repo URL (e.g., TestPyPI)
    - twine_exe: str (default 'python -m twine') – how to invoke twine
    - extra_args: List[str] – e.g., ['--skip-existing']

    Auth:
    - TWINE_USERNAME / TWINE_PASSWORD or TWINE_API_TOKEN env variables are commonly used.
    """

    def publish(self, artifacts: Sequence[PathLike]) -> List[Dict[str, Any]]:
        import glob
        cfg = self.config
        dist_glob = cfg.get("dist_glob", "dist/*")
        repository_url = cfg.get("repository_url")
        twine_exe = cfg.get("twine_exe", "python -m twine")
        extra = cfg.get("extra_args") or []

        files = list(glob.glob(dist_glob))
        if not files:
            return [{"artifact": dist_glob, "status": "error", "error": "No distribution files matched"}]

        cmd = twine_exe.split() + ["upload"]
        if repository_url:
            cmd += ["--repository-url", repository_url]
        cmd += extra
        cmd += files
        try:
            cp = subprocess.run(cmd, capture_output=True, text=True, check=False)
            status = "success" if cp.returncode == 0 else "error"
            results = []
            for f in files:
                results.append({
                    "artifact": f,
                    "status": status,
                    "details": {"stdout": cp.stdout, "stderr": cp.stderr, "returncode": cp.returncode},
                })
            return results
        except Exception as e:  # noqa: BLE001
            return [{"artifact": f, "status": "error", "error": str(e)} for f in files]


class ContainerRegistryDestination(Destination):
    """Push arbitrary artifacts to an OCI-compliant registry using the `oras` CLI.

    This destination is registry-agnostic: it works with any OCI-compatible
    registry (Docker Hub, GHCR, ECR, GCR, ACR, Harbor, etc.). It does not
    require Docker to be installed.

    Config:
    - ref: str (required) – target OCI reference, e.g. 'ghcr.io/org/artifacts:v1'
    - tool: str (default 'oras') – currently only 'oras' is supported
    - artifact_type: str (optional) – sets the artifact type for the manifest, e.g.
      'application/vnd.acme.thing.v1+json'
    - extra_args: List[str] – additional flags to pass to the CLI
    - env: dict – extra environment variables for the subprocess
    - cwd: str – working directory
    - timeout: float – seconds to wait for the command

    Notes:
    - Authentication is handled by the CLI (e.g., `oras login` or registry-specific
      environment variables). This destination does not manage credentials.
    - All provided artifacts are pushed under a single reference in one call,
      which is the common ORAS usage pattern. Results are returned per artifact
      with a uniform status.
    """

    def publish(self, artifacts: Sequence[PathLike]) -> List[Dict[str, Any]]:
        cfg = self.config
        ref = cfg.get("ref")
        if not ref:
            raise ValueError("ContainerRegistryDestination requires config['ref'] (OCI reference)")
        tool = (cfg.get("tool") or "oras").lower()
        if tool != "oras":
            raise ValueError("ContainerRegistryDestination currently supports tool='oras' only")

        artifact_type = cfg.get("artifact_type")
        extra = list(cfg.get("extra_args") or [])
        cwd = cfg.get("cwd")
        timeout = cfg.get("timeout")
        env = os.environ.copy()
        env.update(cfg.get("env", {}))

        paths = self._as_paths(artifacts)
        if not paths:
            return []

        cmd: List[str] = ["oras", "push", str(ref)]
        if artifact_type:
            cmd += ["--artifact-type", artifact_type]
        cmd += [str(p) for p in paths]
        cmd += extra

        try:
            cp = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=env, timeout=timeout, check=False)
            status = "success" if cp.returncode == 0 else "error"
            details = {"stdout": cp.stdout, "stderr": cp.stderr, "returncode": cp.returncode}
            return [{"artifact": str(p), "status": status, "details": details} for p in paths]
        except Exception as e:  # noqa: BLE001
            return [{"artifact": str(p), "status": "error", "error": str(e)} for p in paths]


class GitHubReleaseDestination(Destination):
    """Create or reuse a GitHub Release and upload assets.

    Config:
    - owner: str – repository owner
    - repo: str – repository name
    - tag: str – tag name for the release
    - title: str (optional) – release title (defaults to tag)
    - body: str (optional) – release notes
    - draft: bool (default False)
    - prerelease: bool (default False)
    - overwrite_assets: bool (default True) – if asset with same name exists, delete and re-upload

    Auth:
    - Use env GITHUB_TOKEN with repo scope.
    """

    api_base = "https://api.github.com"
    upload_base = "https://uploads.github.com"

    def _request(self, method: str, url: str, token: str, data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Tuple[int, Dict[str, Any]]:
        h = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}", "X-GitHub-Api-Version": "2022-11-28"}
        if headers:
            h.update(headers)
        body: Optional[bytes] = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            h.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(url=url, data=body, headers=h, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read().decode("utf-8")
                status = resp.getcode() or 0
                return status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8") if e.read else ""
            try:
                parsed = json.loads(raw) if raw else {"message": str(e)}
            except Exception:
                parsed = {"message": raw or str(e)}
            return e.code, parsed

    def publish(self, artifacts: Sequence[PathLike]) -> List[Dict[str, Any]]:
        cfg = self.config
        owner = cfg.get("owner")
        repo = cfg.get("repo")
        tag = cfg.get("tag")
        title = cfg.get("title") or tag
        body = cfg.get("body")
        draft = bool(cfg.get("draft", False))
        prerelease = bool(cfg.get("prerelease", False))
        overwrite = bool(cfg.get("overwrite_assets", True))
        token = os.environ.get("GITHUB_TOKEN") or cfg.get("token")
        if not (owner and repo and tag and token):
            raise ValueError("GitHubReleaseDestination requires owner, repo, tag and GITHUB_TOKEN (or config token)")

        # Find or create release
        status, release = self._request("GET", f"{self.api_base}/repos/{owner}/{repo}/releases/tags/{urllib.parse.quote(tag)}", token)
        if status == 404:
            status, release = self._request("POST", f"{self.api_base}/repos/{owner}/{repo}/releases", token, data={
                "tag_name": tag,
                "name": title,
                "body": body or "",
                "draft": draft,
                "prerelease": prerelease,
            })
        if not (200 <= status < 300):
            # Failed to get or create release
            return [{"artifact": str(a), "status": "error", "error": f"release error: {release}"} for a in artifacts]

        upload_url = release.get("upload_url", "").split("{", 1)[0]
        # Fetch existing assets
        assets = release.get("assets")
        if assets is None:
            # Query assets endpoint
            status_assets, assets = self._request("GET", f"{self.api_base}/repos/{owner}/{repo}/releases/{release['id']}/assets", token)
            if not (200 <= status_assets < 300):
                assets = []

        existing = {a.get("name"): a for a in (assets or [])}
        results: List[Dict[str, Any]] = []
        for p in self._as_paths(artifacts):
            name = p.name
            # Optionally delete existing asset with the same name
            if overwrite and name in existing:
                asset_id = existing[name].get("id")
                if asset_id:
                    self._request("DELETE", f"{self.api_base}/repos/{owner}/{repo}/releases/assets/{asset_id}", token)
            # Upload
            content_type = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
            with open(p, "rb") as fh:
                data = fh.read()
            url = f"{upload_url}?name={urllib.parse.quote(name)}"
            status_up, resp = self._request(
                "POST",
                url,
                token,
                data=None,
                headers={"Content-Type": content_type, "Content-Length": str(len(data))},
            )
            # urllib Request doesn't support sending both headers and raw body with our helper easily; do manual upload
            try:
                req = urllib.request.Request(url=url, data=data, headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": content_type,
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                }, method="POST")
                with urllib.request.urlopen(req) as r:
                    raw = r.read().decode("utf-8")
                    results.append({"artifact": str(p), "status": "success", "details": json.loads(raw) if raw else {}})
            except urllib.error.HTTPError as e:
                raw = e.read().decode("utf-8") if getattr(e, 'read', None) else ""
                results.append({"artifact": str(p), "status": "error", "error": raw or str(e)})
            except Exception as e:  # noqa: BLE001
                results.append({"artifact": str(p), "status": "error", "error": str(e)})
        return results


class SlackDestination(Destination):
    """Send notifications to Slack via webhook.

    Config:
    - webhook_url: str (required) – Slack webhook URL
    - channel: str (optional) – Override default channel (#channel or @user)
    - username: str (optional) – Bot username
    - icon_emoji: str (optional) – Bot icon emoji (e.g., ':robot_face:')
    - message_template: str (optional) – Message template with {artifact} placeholder
    - on_events: List[str] (optional) – Event types to notify on
      (evolution.completed, evolution.failed, generation.promoted)

    Notes:
    - artifacts parameter is treated as a list of event payloads (dicts as JSON strings)
    - Each artifact should be a JSON string containing event data
    - Returns one result per notification sent
    """

    def publish(self, artifacts: Sequence[PathLike]) -> List[Dict[str, Any]]:
        cfg = self.config
        webhook_url = cfg.get("webhook_url")
        if not webhook_url:
            raise ValueError("SlackDestination requires config['webhook_url']")

        channel = cfg.get("channel")
        username = cfg.get("username", "Gryt CI")
        icon_emoji = cfg.get("icon_emoji", ":robot_face:")
        message_template = cfg.get("message_template", "Artifact: {artifact}")

        results: List[Dict[str, Any]] = []

        for artifact in artifacts:
            try:
                # If artifact is a path, read it; otherwise treat as event payload
                artifact_str = str(artifact)
                try:
                    artifact_path = Path(artifact)
                    if artifact_path.exists():
                        with open(artifact_path, "r") as f:
                            event_data = json.loads(f.read())
                        message = self._format_event_message(event_data, message_template)
                    else:
                        # Treat as JSON string
                        event_data = json.loads(artifact_str)
                        message = self._format_event_message(event_data, message_template)
                except (json.JSONDecodeError, OSError):
                    # Fallback: use template with artifact path
                    message = message_template.format(artifact=artifact_str)

                # Build Slack payload
                payload: Dict[str, Any] = {
                    "text": message,
                    "username": username,
                    "icon_emoji": icon_emoji,
                }
                if channel:
                    payload["channel"] = channel

                # Send to Slack
                body = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    url=webhook_url,
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )

                with urllib.request.urlopen(req, timeout=10) as resp:
                    status_code = resp.getcode()
                    if status_code == 200:
                        results.append({
                            "artifact": artifact_str,
                            "status": "success",
                            "details": {"message": message},
                        })
                    else:
                        results.append({
                            "artifact": artifact_str,
                            "status": "error",
                            "error": f"Slack returned status {status_code}",
                        })

            except urllib.error.HTTPError as e:
                results.append({
                    "artifact": str(artifact),
                    "status": "error",
                    "error": f"HTTP {e.code}: {e.reason}",
                })
            except Exception as e:  # noqa: BLE001
                results.append({
                    "artifact": str(artifact),
                    "status": "error",
                    "error": str(e),
                })

        return results

    def _format_event_message(self, event_data: Dict[str, Any], template: str) -> str:
        """Format event data into a Slack message"""
        event_type = event_data.get("event_type", "unknown")

        if event_type == "evolution.completed":
            evolution = event_data.get("evolution", {})
            return f"✓ Evolution completed: {evolution.get('tag', '?')} - {evolution.get('status', '?')}"
        elif event_type == "evolution.failed":
            evolution = event_data.get("evolution", {})
            return f"✗ Evolution failed: {evolution.get('tag', '?')}"
        elif event_type == "generation.promoted":
            generation = event_data.get("generation", {})
            return f"🚀 Generation promoted: {generation.get('version', '?')}"
        else:
            # Use template
            return template.format(artifact=json.dumps(event_data))


class PrometheusDestination(Destination):
    """Push metrics to Prometheus Pushgateway.

    Config:
    - pushgateway_url: str (required) – Pushgateway URL (e.g., http://localhost:9091)
    - job_name: str (default 'gryt_ci') – Prometheus job name
    - instance: str (optional) – Instance label
    - metrics: Dict[str, Any] (required) – Metrics to push, format:
      {
        "metric_name": {
          "type": "gauge" | "counter" | "histogram",
          "value": <number>,
          "help": "Metric description",
          "labels": {"label1": "value1", ...}
        }
      }
    - extra_labels: Dict[str, str] (optional) – Additional labels for all metrics
    - timeout: float (default 10) – Request timeout in seconds

    Notes:
    - Uses Prometheus text format for pushing metrics
    - artifacts parameter is ignored; metrics come from config
    - Returns a single result for the push operation
    """

    def publish(self, artifacts: Sequence[PathLike]) -> List[Dict[str, Any]]:
        cfg = self.config
        pushgateway_url = cfg.get("pushgateway_url")
        if not pushgateway_url:
            raise ValueError("PrometheusDestination requires config['pushgateway_url']")

        job_name = cfg.get("job_name", "gryt_ci")
        instance = cfg.get("instance")
        metrics = cfg.get("metrics")
        if not metrics:
            raise ValueError("PrometheusDestination requires config['metrics']")

        extra_labels = cfg.get("extra_labels", {})
        timeout = cfg.get("timeout", 10)

        try:
            # Build Prometheus text format
            lines: List[str] = []

            for metric_name, metric_data in metrics.items():
                metric_type = metric_data.get("type", "gauge")
                metric_value = metric_data.get("value")
                metric_help = metric_data.get("help", f"{metric_name} metric")
                metric_labels = metric_data.get("labels", {})

                # Merge labels
                all_labels = {**extra_labels, **metric_labels}

                # Add TYPE and HELP
                lines.append(f"# TYPE {metric_name} {metric_type}")
                lines.append(f"# HELP {metric_name} {metric_help}")

                # Add metric with labels
                if all_labels:
                    label_str = ",".join([f'{k}="{v}"' for k, v in all_labels.items()])
                    lines.append(f"{metric_name}{{{label_str}}} {metric_value}")
                else:
                    lines.append(f"{metric_name} {metric_value}")

            body = "\n".join(lines).encode("utf-8")

            # Build pushgateway URL with job and instance
            url = f"{pushgateway_url.rstrip('/')}/metrics/job/{urllib.parse.quote(job_name)}"
            if instance:
                url += f"/instance/{urllib.parse.quote(instance)}"

            # Push to Pushgateway
            req = urllib.request.Request(
                url=url,
                data=body,
                headers={"Content-Type": "text/plain; charset=utf-8"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status_code = resp.getcode()
                if status_code in (200, 202):
                    return [{
                        "artifact": "prometheus_metrics",
                        "status": "success",
                        "details": {
                            "job": job_name,
                            "instance": instance,
                            "metrics_count": len(metrics),
                        },
                    }]
                else:
                    return [{
                        "artifact": "prometheus_metrics",
                        "status": "error",
                        "error": f"Pushgateway returned status {status_code}",
                    }]

        except urllib.error.HTTPError as e:
            return [{
                "artifact": "prometheus_metrics",
                "status": "error",
                "error": f"HTTP {e.code}: {e.reason}",
            }]
        except Exception as e:  # noqa: BLE001
            return [{
                "artifact": "prometheus_metrics",
                "status": "error",
                "error": str(e),
            }]
