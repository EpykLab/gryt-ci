import tempfile
import os
import base64

from ..step  import Step, CommandStep

from typing import Dict, Any, List
from enum import Enum


class Modes(Enum):
    path = "path"
    b64 = "b64"

class ScytheValidator(Step):
    def run(self) -> Dict[str, Any]:
        cfg = self.config

        # configs
        mode: Modes = cfg.get("mode", "path")
        path: Any = cfg.get("path", "")
        content: str = cfg.get("content", "")
        gate: bool = cfg.get("gate", True)
        scythe_args: List[str] = cfg.get("scythe_args", [""])

        cmd: List[str] = ["scythe", "run"] + [path] + scythe_args + (["--gate-version"] if gate else [])

        if mode == Modes.path:
            path = str(path)
        elif mode == Modes.b64:
            fd, path = tempfile.mkstemp(suffix=".py")
            decoded = base64.b64decode(content)
            with os.fdopen(fd, "w+") as tmp_file:
                _ = tmp_file.write(decoded.decode("utf-8"))
                tmp_file.flush()

        _cs = CommandStep(
            id=f"{self.id}__scythe",
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
