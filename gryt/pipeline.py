from __future__ import annotations

import concurrent.futures
from typing import Any, Dict, List, Optional

from .data import Data
from .runner import Runner
from .runtime import Runtime
from .versioning import Versioning


class Pipeline:
    """Compose multiple runners into a pipeline."""

    def __init__(
        self,
        runners: List[Runner],
        data: Optional[Data] = None,
        runtime: Optional[Runtime] = None,
        versioning: Optional[Versioning] = None,
        hook: Optional["Hook"] = None,
        destinations: Optional[List["Destination"]] = None,
    ) -> None:
        self.runners = runners
        self.data = data
        self.runtime = runtime
        self.versioning = versioning
        self.hook = hook
        self.destinations = destinations or []

    def execute(self, parallel: bool = False, artifacts: Optional[List["PathLike"]] = None) -> Dict[str, Any]:
        # Inject pipeline-level hook and data into steps if missing
        for r in self.runners:
            for s in getattr(r, "steps", []):
                if self.data is not None and s.data is None:
                    s.data = self.data
                if self.hook is not None and getattr(s, "hook", None) is None:
                    s.hook = self.hook
        if self.hook:
            try:
                self.hook.on_pipeline_start(self, context=None)
            except Exception:
                pass
        if self.runtime:
            self.runtime.provision()
        try:
            if parallel:
                with concurrent.futures.ThreadPoolExecutor() as ex:
                    futures = [ex.submit(r.execute) for r in self.runners]
                    results = {f"runner_{i}": fut.result() for i, fut in enumerate(futures)}
            else:
                results = {f"runner_{i}": r.execute() for i, r in enumerate(self.runners)}
            # Optional publishing to destinations
            publish_results: Dict[str, Any] = {}
            if self.destinations and artifacts:
                for dest in self.destinations:
                    try:
                        dest_res = dest.publish(artifacts)
                        publish_results[dest.id] = dest_res
                    except Exception as e:  # noqa: BLE001
                        publish_results[dest.id] = [{"status": "error", "error": str(e)}]
            if self.hook:
                try:
                    # enrich results with publish info if present
                    final = {"runners": results}
                    if publish_results:
                        final["destinations"] = publish_results
                    self.hook.on_pipeline_end(self, final, context=None)
                except Exception:
                    pass
            # Return combined results
            if publish_results:
                return {"runners": results, "destinations": publish_results}
            return results
        except Exception as e:  # noqa: BLE001
            if self.hook:
                try:
                    self.hook.on_error("pipeline", e, context=None)
                except Exception:
                    pass
            raise
        finally:
            if self.runtime:
                self.runtime.teardown()
