from __future__ import annotations

from typing import Any, Dict

from ..step import CommandStep, Step


class NpmInstallStep(Step):
    """Run `npm ci` if lockfile exists and not disabled, otherwise `npm install`.

    Config:
    - use_ci: bool (default True) – prefer `npm ci`
    - cwd, env, timeout, retries – standard
    """

    def run(self) -> Dict[str, Any]:
        import os

        cfg = self.config
        use_ci = bool(cfg.get("use_ci", True))
        cwd = cfg.get("cwd")
        lock_exists = False
        if cwd:
            lock_exists = os.path.exists(os.path.join(cwd, "package-lock.json")) or os.path.exists(
                os.path.join(cwd, "pnpm-lock.yaml")
            )
        else:
            lock_exists = any(
                os.path.exists(fname) for fname in ["package-lock.json", "pnpm-lock.yaml"]
            )

        cmd = ["npm", "ci"] if (use_ci and lock_exists) else ["npm", "install"]

        _cs = CommandStep(
            id=f"{self.id}__npminstall",
            config={
                "cmd": cmd,
                "cwd": cwd,
                "env": cfg.get("env"),
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

class NpmBuildStep(Step):
    """Run `<node package manager> run <script>` to build a Node project.

    Config:
        - package_manager: str (default npm)
    """


    def run(self) -> Dict[str, Any]:
        cfg = self.config
        script = cfg.get("script", "build")
        package_manager = cfg.get("package_manager", "npm")
        cmd = [package_manager, "run", script]
        _cs = CommandStep(
            id=f"{self.id}__npmbuild",
            config={
                "cmd": cmd,
                "cwd": cfg.get("cwd"),
                "env": cfg.get("env"),
            }
        )
        try:
            setattr(_cs, "show", bool(getattr(self, "show", False)))
        except Exception:
            pass
        return _cs.run()


class SvelteBuildStep(Step):
    """Run `npm run <script>` to build Svelte project.

    Config:
    - script: str (default 'build') – npm script to run
    - cwd, env, timeout, retries – standard
    """

    def run(self) -> Dict[str, Any]:
        cfg = self.config
        script = cfg.get("script", "build")
        cmd = ["npm", "run", script]
        _cs = CommandStep(
            id=f"{self.id}__sveltebuild",
            config={
                "cmd": cmd,
                "cwd": cfg.get("cwd"),
                "env": cfg.get("env"),
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
