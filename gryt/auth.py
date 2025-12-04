from __future__ import annotations

import os
import subprocess
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from .data import Data
from .step import CommandStep


class Auth(ABC):
    """Base class for authentication mechanisms.

    Auth instances can be associated with steps that require authentication
    before execution. This is especially useful in cloud/CI environments where
    credentials need to be dynamically configured.
    """

    def __init__(self, id: str, config: Optional[Dict[str, Any]] = None, data: Optional[Data] = None) -> None:
        self.id = id
        self.config = config or {}
        self.data = data
        self._authenticated = False

    @abstractmethod
    def authenticate(self) -> Dict[str, Any]:
        """Perform authentication and return result.

        Returns:
            Dict with status and any relevant output/error info.
        """

    def is_authenticated(self) -> bool:
        """Check if already authenticated."""
        return self._authenticated

    def mark_authenticated(self) -> None:
        """Mark this auth as completed."""
        self._authenticated = True


class FlyAuth(Auth):
    """Authenticate to Fly.io using API token.

    Config:
    - token_env_var: str - Environment variable name containing the Fly.io API token
                          (default: "FLY_API_TOKEN")
    - timeout: float - Optional timeout in seconds for the auth command
    """

    def authenticate(self) -> Dict[str, Any]:
        """Authenticate to Fly.io using the API token from environment variable."""
        if self._authenticated:
            return {
                "status": "success",
                "message": "Already authenticated",
                "skipped": True
            }

        token_env_var = self.config.get("token_env_var", "FLY_API_TOKEN")
        timeout = self.config.get("timeout")

        # Get token from environment
        token = os.environ.get(token_env_var)
        if not token:
            error_msg = f"Fly.io API token not found in environment variable: {token_env_var}"
            result = {
                "status": "error",
                "error": error_msg,
                "token_env_var": token_env_var
            }
            if self.data:
                self.data.insert(
                    "auth_output",
                    {
                        "auth_id": self.id,
                        "type": "FlyAuth",
                        "output_json": result,
                        "status": "error",
                    }
                )
            return result

        # Authenticate using fly auth token command
        # This command reads from stdin, so we'll use Popen to pipe the token
        try:
            proc = subprocess.Popen(
                ["fly", "auth", "token"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            stdout, stderr = proc.communicate(input=token, timeout=timeout)

            if proc.returncode == 0:
                self._authenticated = True
                result = {
                    "status": "success",
                    "message": "Successfully authenticated to Fly.io",
                    "stdout": stdout.strip(),
                    "stderr": stderr.strip()
                }
                if self.data:
                    self.data.insert(
                        "auth_output",
                        {
                            "auth_id": self.id,
                            "type": "FlyAuth",
                            "output_json": result,
                            "status": "success",
                        }
                    )
                return result
            else:
                error_msg = f"Fly.io authentication failed: {stderr}"
                result = {
                    "status": "error",
                    "error": error_msg,
                    "stdout": stdout.strip(),
                    "stderr": stderr.strip(),
                    "returncode": proc.returncode
                }
                if self.data:
                    self.data.insert(
                        "auth_output",
                        {
                            "auth_id": self.id,
                            "type": "FlyAuth",
                            "output_json": result,
                            "status": "error",
                        }
                    )
                return result

        except subprocess.TimeoutExpired:
            error_msg = "Fly.io authentication timed out"
            result = {
                "status": "error",
                "error": error_msg
            }
            if self.data:
                self.data.insert(
                    "auth_output",
                    {
                        "auth_id": self.id,
                        "type": "FlyAuth",
                        "output_json": result,
                        "status": "error",
                    }
                )
            return result
        except Exception as e:
            error_msg = f"Fly.io authentication error: {str(e)}"
            result = {
                "status": "error",
                "error": error_msg
            }
            if self.data:
                self.data.insert(
                    "auth_output",
                    {
                        "auth_id": self.id,
                        "type": "FlyAuth",
                        "output_json": result,
                        "status": "error",
                    }
                )
            return result


class DockerRegistryAuth(Auth):
    """Authenticate to a Docker container registry.

    Config:
    - registry: str - Registry URL (e.g., "ghcr.io", "docker.io", "registry.gitlab.com")
                     (default: "docker.io")
    - username_env_var: str - Environment variable containing the registry username
                             (default: "DOCKER_USERNAME")
    - token_env_var: str - Environment variable containing the registry token/password
                          (default: "DOCKER_TOKEN")
    - timeout: float - Optional timeout in seconds for the login command
    """

    def authenticate(self) -> Dict[str, Any]:
        """Authenticate to Docker registry using credentials from environment variables."""
        if self._authenticated:
            return {
                "status": "success",
                "message": "Already authenticated",
                "skipped": True
            }

        registry = self.config.get("registry", "docker.io")
        username_env_var = self.config.get("username_env_var", "DOCKER_USERNAME")
        token_env_var = self.config.get("token_env_var", "DOCKER_TOKEN")
        timeout = self.config.get("timeout")

        # Get credentials from environment
        username = os.environ.get(username_env_var)
        token = os.environ.get(token_env_var)

        if not username:
            error_msg = f"Docker username not found in environment variable: {username_env_var}"
            result = {
                "status": "error",
                "error": error_msg,
                "username_env_var": username_env_var
            }
            if self.data:
                self.data.insert(
                    "auth_output",
                    {
                        "auth_id": self.id,
                        "type": "DockerRegistryAuth",
                        "output_json": result,
                        "status": "error",
                    }
                )
            return result

        if not token:
            error_msg = f"Docker token not found in environment variable: {token_env_var}"
            result = {
                "status": "error",
                "error": error_msg,
                "token_env_var": token_env_var
            }
            if self.data:
                self.data.insert(
                    "auth_output",
                    {
                        "auth_id": self.id,
                        "type": "DockerRegistryAuth",
                        "output_json": result,
                        "status": "error",
                    }
                )
            return result

        # Authenticate using docker login with --password-stdin
        try:
            proc = subprocess.Popen(
                ["docker", "login", registry, "--username", username, "--password-stdin"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            stdout, stderr = proc.communicate(input=token, timeout=timeout)

            if proc.returncode == 0:
                self._authenticated = True
                result = {
                    "status": "success",
                    "message": f"Successfully authenticated to {registry}",
                    "registry": registry,
                    "stdout": stdout.strip(),
                    "stderr": stderr.strip()
                }
                if self.data:
                    self.data.insert(
                        "auth_output",
                        {
                            "auth_id": self.id,
                            "type": "DockerRegistryAuth",
                            "output_json": result,
                            "status": "success",
                        }
                    )
                return result
            else:
                error_msg = f"Docker registry authentication failed for {registry}: {stderr}"
                result = {
                    "status": "error",
                    "error": error_msg,
                    "registry": registry,
                    "stdout": stdout.strip(),
                    "stderr": stderr.strip(),
                    "returncode": proc.returncode
                }
                if self.data:
                    self.data.insert(
                        "auth_output",
                        {
                            "auth_id": self.id,
                            "type": "DockerRegistryAuth",
                            "output_json": result,
                            "status": "error",
                        }
                    )
                return result

        except subprocess.TimeoutExpired:
            error_msg = f"Docker registry authentication timed out for {registry}"
            result = {
                "status": "error",
                "error": error_msg,
                "registry": registry
            }
            if self.data:
                self.data.insert(
                    "auth_output",
                    {
                        "auth_id": self.id,
                        "type": "DockerRegistryAuth",
                        "output_json": result,
                        "status": "error",
                    }
                )
            return result
        except Exception as e:
            error_msg = f"Docker registry authentication error for {registry}: {str(e)}"
            result = {
                "status": "error",
                "error": error_msg,
                "registry": registry
            }
            if self.data:
                self.data.insert(
                    "auth_output",
                    {
                        "auth_id": self.id,
                        "type": "DockerRegistryAuth",
                        "output_json": result,
                        "status": "error",
                    }
                )
            return result
