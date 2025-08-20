from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..step import CommandStep, Step


class CargoBuildStep(Step):
    """Run `cargo build`.

    Config:
    - release: bool (optional) – if True, add '--release'
    - all_features: bool (optional) – if True, add '--all-features'
    - features: List[str] (optional) – pass as '--features <comma,separated>'
    - target: str (optional) – '--target <triple>'
    - cwd, env, timeout, retries – standard
    """

    def run(self) -> Dict[str, Any]:
        cfg = self.config
        release = bool(cfg.get("release", False))
        all_features = bool(cfg.get("all_features", False))
        features: List[str] = cfg.get("features") or []
        target: Optional[str] = cfg.get("target")

        cmd: List[str] = ["cargo", "build"]
        if release:
            cmd.append("--release")
        if all_features:
            cmd.append("--all-features")
        if features:
            cmd += ["--features", ",".join(features)]
        if target:
            cmd += ["--target", target]

        return CommandStep(
            id=f"{self.id}__cargobuild",
            config={
                "cmd": cmd,
                "cwd": cfg.get("cwd"),
                "env": cfg.get("env"),
                "timeout": cfg.get("timeout"),
                "retries": cfg.get("retries", 0),
            },
            data=self.data,
        ).run()


class CargoTestStep(Step):
    """Run `cargo test`.

    Config:
    - release: bool (optional)
    - all_features: bool (optional)
    - features: List[str] (optional)
    - workspace: bool (optional) – if True, add '--workspace'
    - cwd, env, timeout, retries – standard
    """

    def run(self) -> Dict[str, Any]:
        cfg = self.config
        release = bool(cfg.get("release", False))
        all_features = bool(cfg.get("all_features", False))
        features: List[str] = cfg.get("features") or []
        workspace = bool(cfg.get("workspace", False))

        cmd: List[str] = ["cargo", "test"]
        if release:
            cmd.append("--release")
        if workspace:
            cmd.append("--workspace")
        if all_features:
            cmd.append("--all-features")
        if features:
            cmd += ["--features", ",".join(features)]

        return CommandStep(
            id=f"{self.id}__cargotest",
            config={
                "cmd": cmd,
                "cwd": cfg.get("cwd"),
                "env": cfg.get("env"),
                "timeout": cfg.get("timeout"),
                "retries": cfg.get("retries", 0),
            },
            data=self.data,
        ).run()
