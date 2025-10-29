"""Client for Gryt Cloud API."""
from __future__ import annotations
import hashlib
import hmac
from datetime import datetime, timezone
from typing import Any, Optional
import requests
from requests.auth import AuthBase, HTTPBasicAuth


class HmacAuth(AuthBase):
    """HMAC authentication for requests."""

    def __init__(self, key_id: str, secret: str):
        self.key_id = key_id
        self.secret = secret

    def __call__(self, r: requests.PreparedRequest) -> requests.PreparedRequest:
        method = r.method.upper()
        path = r.path_url
        timestamp = datetime.now(timezone.utc).isoformat()
        body = r.body.decode('utf-8', 'ignore') if r.body else ""

        message = f"{method}\n{path}\n{timestamp}\n{body}"
        signature = hmac.new(self.secret.encode(), message.encode(), hashlib.sha256).hexdigest()

        r.headers["Authorization"] = f"HMAC {self.key_id}:{timestamp}:{signature}"
        return r


class GrytCloudClient:
    """Client for interacting with Gryt Cloud API."""

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        gryt_url: Optional[str] = None,
        api_key_id: Optional[str] = None,
        api_key_secret: Optional[str] = None,
    ):
        self.username = username
        self.password = password
        self.gryt_url = gryt_url.rstrip("/") if gryt_url else "https://api.gryt.dev"
        self.api_key_id = api_key_id
        self.api_key_secret = api_key_secret
        self.session = requests.Session()

    def _get_auth(self) -> Optional[AuthBase]:
        """Get an auth handler for the request."""
        if self.api_key_id and self.api_key_secret:
            return HmacAuth(self.api_key_id, self.api_key_secret)
        if self.username and self.password:
            return HTTPBasicAuth(self.username, self.password)
        return None

    def _request(
        self,
        method: str,
        path: str,
        json: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
        require_auth: bool = True,
    ) -> dict[str, Any]:
        """Make a request to the API."""
        url = f"{self.gryt_url}{path}"
        auth = self._get_auth() if require_auth else None

        if require_auth and not auth:
            raise RuntimeError("Authentication required. Please configure credentials with 'gryt cloud login'")

        try:
            response = self.session.request(
                method=method,
                url=url,
                json=json,
                params=params,
                auth=auth,
                timeout=60,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_msg = f"API request failed: {e}"
            try:
                error_data = e.response.json()
                if "detail" in error_data:
                    error_msg = f"API error: {error_data['detail']}"
            except Exception:
                pass
            raise RuntimeError(error_msg) from e
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Request failed: {e}") from e

    # Account Management
    def create_account(self, username: str, password: str) -> dict[str, Any]:
        """Create a new user account."""
        return self._request(
            "POST",
            "/api/v1/accounts/create",
            json={"username": username, "password": password},
            require_auth=False,
        )

    # Pipelines
    def list_pipelines(self) -> dict[str, Any]:
        """List user's pipelines."""
        return self._request("GET", "/api/v1/pipelines")

    def create_pipeline(self, name: str, description: str = "", config: str = "") -> dict[str, Any]:
        """Create a new pipeline."""
        return self._request(
            "POST",
            "/api/v1/pipelines",
            json={"name": name, "description": description, "config": config},
        )

    def get_pipeline(self, pipeline_id: str) -> dict[str, Any]:
        """Get a specific pipeline."""
        return self._request("GET", f"/api/v1/pipelines/{pipeline_id}")

    def delete_pipeline(self, pipeline_id: str) -> dict[str, Any]:
        """Delete a specific pipeline."""
        return self._request("DELETE", f"/api/v1/pipelines/{pipeline_id}")

    # GitHub Repositories
    def list_github_repos(self) -> dict[str, Any]:
        """List GitHub repository configurations."""
        return self._request("GET", "/api/v1/github-repos")

    def create_github_repo(
        self,
        name: str,
        git_url: str,
        is_private: bool = False,
        branch: str = "main",
        access_token: Optional[str] = None,
    ) -> dict[str, Any]:
        """Add a GitHub repository."""
        payload: dict[str, Any] = {
            "name": name,
            "git_url": git_url,
            "is_private": is_private,
            "branch": branch,
        }
        if access_token:
            payload["access_token"] = access_token
        return self._request("POST", "/api/v1/github-repos", json=payload)

    def get_github_repo(self, repo_id: str) -> dict[str, Any]:
        """Get a specific GitHub repository configuration."""
        return self._request("GET", f"/api/v1/github-repos/{repo_id}")

    def delete_github_repo(self, repo_id: str) -> dict[str, Any]:
        """Delete a specific GitHub repository configuration."""
        return self._request("DELETE", f"/api/v1/github-repos/{repo_id}")

    # Jobs
    def list_jobs(self) -> dict[str, Any]:
        """List user's jobs."""
        return self._request("GET", "/api/v1/jobs")

    def create_job(
        self,
        name: str,
        description: str,
        pipeline_id: str,
        github_repo_id: Optional[str] = None,
        branch_override: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create a new job."""
        payload: dict[str, Any] = {
            "name": name,
            "description": description,
            "pipeline_id": pipeline_id,
        }
        if github_repo_id:
            payload["github_repo_id"] = github_repo_id
        if branch_override:
            payload["branch_override"] = branch_override
        return self._request("POST", "/api/v1/jobs", json=payload)

    def get_job(self, job_id: str) -> dict[str, Any]:
        """Get a specific job."""
        return self._request("GET", f"/api/v1/jobs/{job_id}")

    def delete_job(self, job_id: str) -> dict[str, Any]:
        """Delete a specific job."""
        return self._request("DELETE", f"/api/v1/jobs/{job_id}")

    # Webhooks
    def list_webhooks(self) -> dict[str, Any]:
        """List user's webhooks."""
        return self._request("GET", "/api/v1/webhooks")

    def create_webhook(self, name: str, description: str, job_id: str) -> dict[str, Any]:
        """Create a webhook."""
        return self._request(
            "POST",
            "/api/v1/webhooks",
            json={"name": name, "description": description, "job_id": job_id},
        )

    def get_webhook(self, webhook_id: str) -> dict[str, Any]:
        """Get a specific webhook."""
        return self._request("GET", f"/api/v1/webhooks/{webhook_id}")

    def delete_webhook(self, webhook_id: str) -> dict[str, Any]:
        """Delete a specific webhook."""
        return self._request("DELETE", f"/api/v1/webhooks/{webhook_id}")

    def trigger_webhook(self, webhook_key: str) -> dict[str, Any]:
        """Trigger a webhook (public endpoint)."""
        return self._request(
            "POST",
            f"/api/v1/webhooks/run/{webhook_key}",
            require_auth=False,
        )

    # API Keys
    def create_api_key(self, name: str, expires_in_days: Optional[int] = None) -> dict[str, Any]:
        """Create a new API key."""
        payload = {"name": name}
        if expires_in_days:
            payload["expires_in_days"] = expires_in_days
        return self._request("POST", "/api/v1/api-keys", json=payload)

    def list_api_keys(self) -> dict[str, Any]:
        """List all API keys."""
        return self._request("GET", "/api/v1/api-keys")

    def revoke_api_key(self, key_id: str) -> dict[str, Any]:
        """Revoke an API key."""
        return self._request("DELETE", f"/api/v1/api-keys/{key_id}")

    # Generations (v0.2.0)
    def create_generation(self, generation_data: dict[str, Any]) -> dict[str, Any]:
        """Create a new generation."""
        return self._request("POST", "/api/v1/generations", json=generation_data)

    def list_generations(self) -> dict[str, Any]:
        """List all generations."""
        return self._request("GET", "/api/v1/generations")

    def get_generation(self, generation_id: str) -> dict[str, Any]:
        """Get a specific generation."""
        return self._request("GET", f"/api/v1/generations/{generation_id}")

    def update_generation(self, generation_id: str, generation_data: dict[str, Any]) -> dict[str, Any]:
        """Update a generation."""
        return self._request("PATCH", f"/api/v1/generations/{generation_id}", json=generation_data)

    def delete_generation(self, generation_id: str) -> dict[str, Any]:
        """Delete a generation."""
        return self._request("DELETE", f"/api/v1/generations/{generation_id}")

    # Evolutions (v0.3.0)
    def create_evolution(self, evolution_data: dict[str, Any]) -> dict[str, Any]:
        """Create a new evolution."""
        return self._request("POST", "/api/v1/evolutions", json=evolution_data)

    def list_evolutions(self, generation_id: Optional[str] = None) -> dict[str, Any]:
        """List all evolutions (optionally filtered by generation)."""
        params = {"generation_id": generation_id} if generation_id else None
        return self._request("GET", "/api/v1/evolutions", params=params)

    def get_evolution(self, evolution_id: str) -> dict[str, Any]:
        """Get a specific evolution."""
        return self._request("GET", f"/api/v1/evolutions/{evolution_id}")

    def update_evolution(self, evolution_id: str, evolution_data: dict[str, Any]) -> dict[str, Any]:
        """Update an evolution."""
        return self._request("PATCH", f"/api/v1/evolutions/{evolution_id}", json=evolution_data)

    def delete_evolution(self, evolution_id: str) -> dict[str, Any]:
        """Delete an evolution."""
        return self._request("DELETE", f"/api/v1/evolutions/{evolution_id}")

    # Apply
    def apply(self, yaml_content: str) -> dict[str, Any]:
        """Apply a YAML configuration."""
        return self._request("POST", "/api/v1/apply", json={"yaml_content": yaml_content})
