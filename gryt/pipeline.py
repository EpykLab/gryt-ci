from __future__ import annotations

import concurrent.futures
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .data import Data
from .runner import Runner
from .runtime import Runtime
from .versioning import Versioning

if TYPE_CHECKING:
    from .auth import Auth


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
        validators: Optional[List["EnvValidator"]] = None,
        auth_steps: Optional[List["Auth"]] = None,
    ) -> None:
        self.runners = runners
        self.data = data
        self.runtime = runtime
        self.versioning = versioning
        self.hook = hook
        self.destinations = destinations or []
        self.validators = validators or []
        self.auth_steps = auth_steps or []

    def validate_environment(self) -> Dict[str, Any]:
        """Run all configured validators and return a report without raising."""
        issues: List[Dict[str, Any]] = []
        for v in self.validators:
            try:
                for iss in v.run():
                    issues.append(
                        {
                            "kind": getattr(iss, "kind", "unknown"),
                            "name": getattr(iss, "name", ""),
                            "message": getattr(iss, "message", ""),
                            "details": getattr(iss, "details", None),
                        }
                    )
            except Exception as e:  # noqa: BLE001
                issues.append({"kind": "validator_error", "name": type(v).__name__, "message": str(e)})
        return {"status": "ok" if not issues else "invalid_env", "issues": issues}

    def execute(self, parallel: bool = False, artifacts: Optional[List["PathLike"]] = None, show: bool = False) -> Dict[str, Any]:
        # Inject pipeline-level hook and data into steps if missing
        for r in self.runners:
            for s in getattr(r, "steps", []):
                if self.data is not None and s.data is None:
                    s.data = self.data
                if self.hook is not None and getattr(s, "hook", None) is None:
                    s.hook = self.hook
                # Propagate show flag to steps (used by CommandStep to dump output)
                try:
                    setattr(s, "show", bool(show))
                except Exception:
                    pass
        # Pre-run environment validation (aggregate issues, no fail-fast)
        if self.validators:
            env_report = self.validate_environment()
            if env_report.get("status") != "ok":
                # Do not proceed with execution; fail early but include all issues
                return env_report

        if self.hook:
            try:
                self.hook.on_pipeline_start(self, context=None)
            except Exception:
                pass

        # Execute all auth steps before anything else
        if self.auth_steps:
            for auth_step in self.auth_steps:
                if not auth_step.is_authenticated():
                    auth_result = auth_step.authenticate()
                    if auth_result.get("status") != "success":
                        # Auth failed, return error immediately
                        return {
                            "status": "error",
                            "error": "Authentication failed",
                            "auth_id": auth_step.id,
                            "auth_result": auth_result
                        }

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
