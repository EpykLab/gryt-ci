from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..step import CommandStep, Step


class GoModDownloadStep(Step):
    """Run `go mod download`.

    Config:
    - cwd: str (optional) – working directory (module root)
    - env: dict[str, str] (optional)
    - timeout: float (optional)
    - retries: int (optional)
    """

    def run(self) -> Dict[str, Any]:
        cfg = self.config
        cmd = ["go", "mod", "download"]
        _cs = CommandStep(
            id=f"{self.id}__gomoddownload",
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


class GoBuildStep(Step):
    """Run `go build`.

    Config:
    - packages: List[str] (default ['./...']) – what to build
    - flags: List[str] (optional) – extra flags (e.g., ['-v'])
    - output: str (optional) – passes as '-o <output>'
    - cwd, env, timeout, retries – standard
    """

    def run(self) -> Dict[str, Any]:
        cfg = self.config
        packages: List[str] = cfg.get("packages") or ["./..."]
        flags: List[str] = cfg.get("flags") or []
        output: Optional[str] = cfg.get("output")

        cmd: List[str] = ["go", "build"] + flags
        if output:
            cmd += ["-o", output]
        cmd += packages

        _cs = CommandStep(
            id=f"{self.id}__gobuild",
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


class GoTestStep(Step):
    """Run `go test`.

    Config:
    - packages: List[str] (default ['./...'])
    - flags: List[str] (optional) – e.g., ['-v']
    - json: bool (optional) – if True, add '-json'
    - cwd, env, timeout, retries – standard
    """

    def run(self) -> Dict[str, Any]:
        cfg = self.config
        packages: List[str] = cfg.get("packages") or ["./..."]
        flags: List[str] = cfg.get("flags") or []
        as_json: bool = bool(cfg.get("json", False))

        cmd: List[str] = ["go", "test"] + flags
        if as_json:
            cmd += ["-json"]
        cmd += packages

        _cs = CommandStep(
            id=f"{self.id}__gotest",
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
