from __future__ import annotations

import subprocess
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from .data import Data
from .hook import Hook


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
        show = bool(getattr(self, "show", False))

        attempt = 0
        last_error: Optional[str] = None
        while attempt <= retries:
            start = time.time()
            stdout_buf: list[str] = []
            stderr_buf: list[str] = []
            try:
                # Use Popen to allow streaming output
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,  # line-buffered
                    env=env,
                    cwd=cwd,
                )

                # Readers for stdout and stderr
                def _read_stream(stream, buf, is_err: bool = False):
                    try:
                        for line in iter(stream.readline, ""):
                            buf.append(line)
                            if show:
                                # Print to appropriate stream while preserving ordering per stream
                                print(line, end="", flush=True)
                    finally:
                        try:
                            stream.close()
                        except Exception:
                            pass

                import threading

                t_out = threading.Thread(target=_read_stream, args=(proc.stdout, stdout_buf, False), daemon=True) if proc.stdout else None
                t_err = threading.Thread(target=_read_stream, args=(proc.stderr, stderr_buf, True), daemon=True) if proc.stderr else None
                if t_out:
                    t_out.start()
                if t_err:
                    t_err.start()

                # Wait for completion with optional timeout
                try:
                    proc.wait(timeout=timeout)
                except Exception as wait_err:  # timeout or others
                    last_error = str(wait_err)
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    proc.wait()

                # Ensure readers finished
                if t_out:
                    t_out.join()
                if t_err:
                    t_err.join()

                duration = time.time() - start
                rc = proc.returncode if proc.returncode is not None else -1
                stdout_text = ("".join(stdout_buf)).strip()
                stderr_text = ("".join(stderr_buf)).strip()

                if rc == 0:
                    result = {
                        "status": "success",
                        "stdout": stdout_text,
                        "stderr": stderr_text,
                        "returncode": rc,
                        "duration": duration,
                        "attempts": attempt + 1,
                    }
                    if self.data:
                        self.data.insert(
                            "steps_output",
                            {
                                "step_id": self.id,
                                "runner_id": None,
                                "name": self.id,
                                "output_json": result,
                                "stdout": stdout_text,
                                "stderr": stderr_text,
                                "status": result.get("status"),
                                "duration": duration,
                            },
                        )
                    return result
                else:
                    # Non-zero exit; possibly retry
                    last_error = f"Process exited with code {rc}"
                    attempt += 1
                    if attempt > retries:
                        result = {
                            "status": "error",
                            "error": last_error,
                            "stdout": stdout_text,
                            "stderr": stderr_text,
                            "returncode": rc,
                            "duration": duration,
                            "attempts": attempt,
                        }
                        if self.data:
                            self.data.insert(
                                "steps_output",
                                {
                                    "step_id": self.id,
                                    "runner_id": None,
                                    "name": self.id,
                                    "output_json": result,
                                    "stdout": stdout_text,
                                    "stderr": stderr_text,
                                    "status": result.get("status"),
                                    "duration": duration,
                                },
                            )
                        return result
                    # else: continue loop to retry
                    continue
            except Exception as e:  # noqa: BLE001
                last_error = str(e)
                attempt += 1
                if attempt > retries:
                    duration = time.time() - start
                    result = {
                        "status": "error",
                        "error": last_error,
                        "stdout": "",
                        "stderr": "",
                        "returncode": None,
                        "duration": duration,
                        "attempts": attempt,
                    }
                    if self.data:
                        self.data.insert(
                            "steps_output",
                            {
                                "step_id": self.id,
                                "runner_id": None,
                                "name": self.id,
                                "output_json": result,
                                "stdout": "",
                                "stderr": "",
                                "status": result.get("status"),
                                "duration": duration,
                            },
                        )
                    return result
        # Fallback (should not reach here)
        return {"status": "error", "error": last_error or "unknown error"}
