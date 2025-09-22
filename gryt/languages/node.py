from __future__ import annotations

from typing import Any, Dict

from ..step import CommandStep, Step


class NpmInstallStep(Step):
    """Run `npm ci` if lockfile exists and not disabled, otherwise `npm install`.

    Config:
    - use_ci: bool (default True) – prefer `npm ci`
    - cwd, env, timeout, retries – standard
    - use_pnpm: bool - use pnpm instead of npm (deprecated; use package_manager)
    - package_manager: str - 'npm' (default) or 'pnpm'
    """

    def run(self) -> Dict[str, Any]:
        import os

        cfg = self.config
        use_ci = bool(cfg.get("use_ci", True))
        cwd = cfg.get("cwd")
        # Prefer explicit package_manager; fall back to legacy use_pnpm flag
        package_manager = (cfg.get("package_manager") or "").strip() or None
        if package_manager:
            pm = package_manager.lower()
        else:
            use_pnpm = bool(cfg.get("use_pnpm", False))
            pm = "pnpm" if use_pnpm else "npm"

        # Select lock files depending on package manager
        lock_files = ["pnpm-lock.yaml"] if pm == "pnpm" else ["package-lock.json", "npm-shrinkwrap.json"]

        if cwd:
            lock_exists = any(os.path.exists(os.path.join(cwd, fname)) for fname in lock_files)
        else:
            lock_exists = any(os.path.exists(fname) for fname in lock_files)

        # Determine the command to use
        if pm == "pnpm":
            # pnpm does not have `ci`; the equivalent is install --frozen-lockfile when a lockfile exists
            cmd = ["pnpm", "install", "--frozen-lockfile"] if (use_ci and lock_exists) else ["pnpm", "install"]
        else:
            cmd = ["npm", "ci"] if (use_ci and lock_exists) else ["npm", "install"]

        # Track whether we used the stricter/frozen variant to allow a fallback
        used_strict = (use_ci and lock_exists)

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
        result = _cs.run()
        try:
            # annotate for easier debugging
            result["executed_cmd"] = " ".join(cmd)
        except Exception:
            pass

        # If the strict mode failed, try a best-effort install with the same package manager
        if used_strict and result.get("status") == "error" and result.get("returncode") == 1:
            fallback_cmd = ["pnpm", "install"] if pm == "pnpm" else ["npm", "install"]
            fallback_cs = CommandStep(
                id=f"{self.id}__npminstall_fallback",
                config={
                    "cmd": fallback_cmd,
                    "cwd": cwd,
                    "env": cfg.get("env"),
                    "timeout": cfg.get("timeout"),
                    "retries": cfg.get("retries", 0),
                },
                data=self.data,
            )
            try:
                setattr(fallback_cs, "show", bool(getattr(self, "show", False)))
            except Exception:
                pass
            fb_res = fallback_cs.run()
            try:
                fb_res["executed_cmd"] = " ".join(fallback_cmd)
            except Exception:
                pass
            return fb_res

        return result

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
