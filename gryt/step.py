from __future__ import annotations

import subprocess
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from .data import Data


class Step(ABC):
    """A granular unit of work.

    Steps should be idempotent where possible and return a structured dict
    that is JSON-serializable.
    """

    def __init__(self, id: str, config: Optional[Dict[str, Any]] = None, data: Optional[Data] = None, hook: Optional["Hook"] = None) -> None:
        self.id = id
        self.config = config or {}
        self.data = data
        self.hook = hook

    @abstractmethod
    def run(self) -> Dict[str, Any]:
        """Execute the step and return structured output."""

    def validate(self) -> bool:
        """Optional pre-run validation hook."""
        return True


class CommandStep(Step):
    """Run a shell command and capture output.

    Config:
    - cmd: list[str] – Required. Command to execute.
    - env: dict[str, str] – Optional environment overrides.
    - timeout: float – Optional timeout in seconds.
    - retries: int – retry count on failure (default 0).
    - cwd: str – optional working directory.
    """

    def run(self) -> Dict[str, Any]:
        cmd = self.config.get("cmd") or []
        if not isinstance(cmd, list) or not cmd:
            return {"status": "error", "error": "CommandStep requires config['cmd'] as non-empty list"}
        env = self.config.get("env")
        timeout = self.config.get("timeout")
        retries = int(self.config.get("retries", 0))
        cwd = self.config.get("cwd")

        attempt = 0
        start = time.time()
        last_error: Optional[str] = None
        while attempt <= retries:
            try:
                completed = subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=timeout,
                    cwd=cwd,
                )
                duration = time.time() - start
                result = {
                    "status": "success",
                    "stdout": completed.stdout.strip(),
                    "stderr": completed.stderr.strip(),
                    "returncode": completed.returncode,
                    "duration": duration,
                    "attempts": attempt + 1,
                }
                if self.data:
                    try:
                        self.data.create_table(
                            "steps_output",
                            {
                                "id": "TEXT PRIMARY KEY",
                                "result": "TEXT",
                                "timestamp": "DATETIME DEFAULT CURRENT_TIMESTAMP",
                            },
                        )
                    except Exception:
                        # Table may already exist, ignore errors here
                        pass
                    self.data.insert("steps_output", {"id": self.id, "result": result})
                return result
            except Exception as e:  # noqa: BLE001
                last_error = str(e)
                attempt += 1
                if attempt > retries:
                    duration = time.time() - start
                    result = {
                        "status": "error",
                        "error": last_error,
                        "returncode": getattr(e, "returncode", None),
                        "duration": duration,
                        "attempts": attempt,
                    }
                    if self.data:
                        try:
                            self.data.create_table(
                                "steps_output",
                                {
                                    "id": "TEXT PRIMARY KEY",
                                    "result": "TEXT",
                                    "timestamp": "DATETIME DEFAULT CURRENT_TIMESTAMP",
                                },
                            )
                        except Exception:
                            pass
                        self.data.insert("steps_output", {"id": self.id, "result": result})
                    return result
