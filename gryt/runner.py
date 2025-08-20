from __future__ import annotations

from typing import Any, Dict, List, Optional

from .data import Data
from .step import Step


class Runner:
    """Sequential runner for a list of steps.

    Config options:
    - fail_fast: bool (default True) – stop on first error
    """

    def __init__(self, steps: List[Step], data: Optional[Data] = None, config: Optional[Dict[str, Any]] = None) -> None:
        self.steps = steps
        self.data = data
        self.config = config or {"fail_fast": True}

    def execute(self) -> Dict[str, Dict[str, Any]]:
        results: Dict[str, Dict[str, Any]] = {}
        for step in self.steps:
            step.data = step.data or self.data
            hook = getattr(step, "hook", None)
            try:
                if hook:
                    try:
                        hook.on_step_start(step, context=None)
                    except Exception:
                        pass
                if not step.validate():
                    results[step.id] = {"status": "skipped", "reason": "validate() returned False"}
                    continue
                res = step.run()
                results[step.id] = res
                if hook:
                    try:
                        hook.on_step_end(step, res, context=None)
                    except Exception:
                        pass
                if res.get("status") == "error" and self.config.get("fail_fast", True):
                    break
            except Exception as e:  # noqa: BLE001
                results[step.id] = {"status": "error", "error": str(e)}
                if hook:
                    try:
                        hook.on_error("step", e, context=None)
                    except Exception:
                        pass
                if self.config.get("fail_fast", True):
                    break
        return results
