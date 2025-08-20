from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..step import CommandStep, Step


class PipInstallStep(Step):
    """Install Python packages using pip.

    Config:
    - requirements: str (optional) – path to requirements.txt; if provided, uses '-r <file>'
    - packages: List[str] (optional) – packages to install when no requirements file
    - upgrade: bool (optional) – add '--upgrade'
    - user: bool (optional) – add '--user'
    - cwd, env, timeout, retries – standard
    """

    def run(self) -> Dict[str, Any]:
        cfg = self.config
        requirements: Optional[str] = cfg.get("requirements")
        packages: List[str] = cfg.get("packages") or []
        upgrade = bool(cfg.get("upgrade", False))
        user = bool(cfg.get("user", False))

        cmd: List[str] = ["python", "-m", "pip", "install"]
        if upgrade:
            cmd.append("--upgrade")
        if user:
            cmd.append("--user")
        if requirements:
            cmd += ["-r", requirements]
        else:
            cmd += packages

        return CommandStep(
            id=f"{self.id}__pipinstall",
            config={
                "cmd": cmd,
                "cwd": cfg.get("cwd"),
                "env": cfg.get("env"),
                "timeout": cfg.get("timeout"),
                "retries": cfg.get("retries", 0),
            },
            data=self.data,
        ).run()


class PytestStep(Step):
    """Run pytest.

    Config:
    - args: List[str] (optional) – extra args, e.g., ['-q'] or ['--maxfail=1']
    - paths: List[str] (optional) – test paths
    - cwd, env, timeout, retries – standard
    """

    def run(self) -> Dict[str, Any]:
        cfg = self.config
        args: List[str] = cfg.get("args") or []
        paths: List[str] = cfg.get("paths") or []

        cmd: List[str] = ["pytest"] + args + paths

        return CommandStep(
            id=f"{self.id}__pytest",
            config={
                "cmd": cmd,
                "cwd": cfg.get("cwd"),
                "env": cfg.get("env"),
                "timeout": cfg.get("timeout"),
                "retries": cfg.get("retries", 0),
            },
            data=self.data,
        ).run()
