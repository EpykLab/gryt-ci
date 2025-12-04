from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..step import CommandStep, Step

if TYPE_CHECKING:
    from ..auth import Auth


class FlyDeployStep(Step):
    """Deploy an application to Fly.io.

    Optional Auth:
    - auth: Auth (optional) – Auth instance (e.g., FlyAuth) to authenticate before deployment.
                              Useful in cloud/CI environments where credentials need to be configured.

    Config:
    - app: str (optional) – Fly.io app name. If not provided, uses app name from fly.toml
    - config: str (optional) – path to fly.toml config file (default: fly.toml)
    - image: str (optional) – pre-built Docker image to deploy (e.g., 'myregistry.io/myapp:v1.0.0')
                              If specified, skips building and deploys the image directly.
                              When using 'image', dockerfile/build_arg/no_cache/remote_only are ignored.
    - strategy: str (optional) – deployment strategy: 'rolling', 'immediate', 'canary', 'bluegreen'
    - remote_only: bool (optional) – perform builds remotely on Fly.io (default: False)
    - no_cache: bool (optional) – do not use build cache (default: False)
    - dockerfile: str (optional) – path to Dockerfile if not in root
    - build_arg: List[str] (optional) – build arguments, e.g., ['VERSION=1.0.0', 'ENV=prod']
    - env: Dict[str, str] (optional) – environment variables to set
    - region: str (optional) – target region for deployment
    - vm_size: str (optional) – VM size (e.g., 'shared-cpu-1x', 'performance-1x')
    - ha: bool (optional) – enable high availability (default: False)
    - auto_confirm: bool (optional) – skip confirmation prompts (default: True)
    - wait_timeout: int (optional) – seconds to wait for deployment to complete (default: 300)
    - cwd: str (optional) – working directory
    - timeout: float (optional) – overall command timeout in seconds
    - retries: int (optional) – retry count on failure (default: 0)
    """

    def __init__(self, id: str, config: Optional[Dict[str, Any]] = None, data: Optional[Any] = None, hook: Optional[Any] = None, auth: Optional["Auth"] = None) -> None:
        super().__init__(id, config, data, hook)
        self.auth = auth

    def run(self) -> Dict[str, Any]:
        # Authenticate if auth is provided
        if self.auth and not self.auth.is_authenticated():
            auth_result = self.auth.authenticate()
            if auth_result.get("status") != "success":
                # Authentication failed, return error
                return {
                    "status": "error",
                    "error": f"Authentication failed: {auth_result.get('error', 'Unknown error')}",
                    "auth_result": auth_result
                }
        cfg = self.config
        app: Optional[str] = cfg.get("app")
        config: str = cfg.get("config", "fly.toml")
        image: Optional[str] = cfg.get("image")
        strategy: Optional[str] = cfg.get("strategy")
        remote_only: bool = cfg.get("remote_only", False)
        no_cache: bool = cfg.get("no_cache", False)
        dockerfile: Optional[str] = cfg.get("dockerfile")
        build_args: List[str] = cfg.get("build_arg") or []
        env_vars: Dict[str, str] = cfg.get("env") or {}
        region: Optional[str] = cfg.get("region")
        vm_size: Optional[str] = cfg.get("vm_size")
        ha: bool = cfg.get("ha", False)
        auto_confirm: bool = cfg.get("auto_confirm", True)
        wait_timeout: int = cfg.get("wait_timeout", 300)

        cmd: List[str] = ["fly", "deploy"]

        # Add app name if specified
        if app:
            cmd += ["--app", app]

        # Add config file
        if config != "fly.toml":
            cmd += ["--config", config]

        # If image is specified, deploy pre-built image directly
        if image:
            cmd.append(f"--image={image}")  # Use equals sign format
            cmd.append("--local-only")  # Tell Fly to use the image without building
        else:
            # Build from source options (only if image not specified)
            # Remote build options
            if remote_only:
                cmd.append("--remote-only")

            # Build cache
            if no_cache:
                cmd.append("--no-cache")

            # Dockerfile path
            if dockerfile:
                cmd += ["--dockerfile", dockerfile]

            # Build arguments
            for build_arg in build_args:
                cmd += ["--build-arg", build_arg]

        # Add deployment strategy
        if strategy:
            cmd += ["--strategy", strategy]

        # Environment variables
        for key, value in env_vars.items():
            cmd += ["--env", f"{key}={value}"]

        # Region
        if region:
            cmd += ["--region", region]

        # VM size
        if vm_size:
            cmd += ["--vm-size", vm_size]

        # High availability
        if ha:
            cmd.append("--ha")

        # Auto-confirm deployment
        if auto_confirm:
            cmd.append("--yes")

        # Wait timeout
        cmd += ["--wait-timeout", str(wait_timeout)]

        # Debug: print the command being executed
        print(f"[FlyDeployStep] Executing command: {' '.join(cmd)}")
        print(f"[FlyDeployStep] Working directory: {cfg.get('cwd')}")

        _cs = CommandStep(
            id=f"{self.id}__flydeploy",
            config={
                "cmd": cmd,
                "cwd": cfg.get("cwd"),
                "env": cfg.get("env_vars"),  # Pass through any shell env vars
                "timeout": cfg.get("timeout"),
                "retries": cfg.get("retries", 0),
            },
            data=self.data,
        )
        try:
            setattr(_cs, "show", bool(getattr(self, "show", False)))
        except Exception:
            pass
        return _cs.run()
