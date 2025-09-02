from __future__ import annotations

import glob
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from .step import Step
from .destination import Destination

PathLike = Union[str, Path]


class PublishDestinationStep(Step):
    """
    Step that publishes artifacts to a Destination.

    Usage:
    - Provide a concrete Destination instance and a list of artifact paths or glob patterns.
    - Returns a dict with overall status and per-artifact results.
    """

    def __init__(
        self,
        id: str,
        destination: Destination,
        artifacts: Sequence[PathLike],
        config: Optional[Dict[str, Any]] = None,
        data: Optional["Data"] = None,
        hook: Optional["Hook"] = None,
    ) -> None:
        super().__init__(id=id, config=config, data=data, hook=hook)
        self.destination = destination
        self.artifacts = list(artifacts)

    def _expand_artifacts(self) -> List[str]:
        files: List[str] = []
        for a in self.artifacts:
            s = str(a)
            if any(ch in s for ch in "*?[]"):
                files.extend(glob.glob(s))
            else:
                files.append(s)
        return files

    def run(self) -> Dict[str, Any]:
        start = time.time()
        paths = self._expand_artifacts()
        try:
            results = self.destination.publish(paths)
            status = "success" if all((r.get("status") == "success") for r in results) else "error"
        except Exception as e:  # noqa: BLE001
            # Destination misconfiguration or unexpected error
            results = [{"artifact": p, "status": "error", "error": str(e)} for p in (paths or [str(a) for a in self.artifacts])]
            status = "error"

        duration = time.time() - start
        output = {"status": status, "results": results, "duration": duration}

        if self.data:
            self.data.insert(
                "steps_output",
                {
                    "step_id": self.id,
                    "runner_id": None,
                    "name": self.id,
                    "output_json": output,
                    "status": status,
                    "duration": duration,
                },
            )
        return output
