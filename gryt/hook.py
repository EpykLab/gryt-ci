from __future__ import annotations

import json
import sys
import traceback
import urllib.request
from abc import ABC
from typing import Any, Dict, Optional


class Hook(ABC):
    """Base Hook with robust, no-op defaults.

    Hooks can observe and interact with pipeline/step execution. Subclasses may
    send or fetch data from remote services (e.g., HTTP) or emit local logs.

    All methods are best-effort and should not raise: the default implementations
    catch and suppress exceptions to avoid breaking the CI flow.
    """

    def on_pipeline_start(self, pipeline: Any, context: Optional[Dict[str, Any]] = None) -> None:  # noqa: D401
        self._safe_noop()

    def on_pipeline_end(self, pipeline: Any, results: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:  # noqa: D401
        self._safe_noop()

    def on_step_start(self, step: Any, context: Optional[Dict[str, Any]] = None) -> None:  # noqa: D401
        self._safe_noop()

    def on_step_end(self, step: Any, result: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:  # noqa: D401
        self._safe_noop()

    def on_error(self, scope: str, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:  # noqa: D401
        self._safe_noop()

    # Helpers
    def _safe_noop(self) -> None:
        return None


class PrintHook(Hook):
    """Simple stdout/stderr hook for local visibility."""

    def __init__(self, stream=None) -> None:
        self.stream = stream or sys.stdout

    def on_pipeline_start(self, pipeline: Any, context: Optional[Dict[str, Any]] = None) -> None:
        try:
            print(f"[hook] pipeline_start: runners={len(getattr(pipeline, 'runners', []))}", file=self.stream)
        except Exception:
            pass

    def on_pipeline_end(self, pipeline: Any, results: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
        try:
            print(f"[hook] pipeline_end: results={json.dumps(results)[:500]}", file=self.stream)
        except Exception:
            pass

    def on_step_start(self, step: Any, context: Optional[Dict[str, Any]] = None) -> None:
        try:
            print(f"[hook] step_start: {getattr(step, 'id', '?')}", file=self.stream)
        except Exception:
            pass

    def on_step_end(self, step: Any, result: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
        try:
            sid = getattr(step, 'id', '?')
            print(f"[hook] step_end: {sid} -> {result.get('status')}", file=self.stream)
        except Exception:
            pass

    def on_error(self, scope: str, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        try:
            print(f"[hook] error in {scope}: {error}\n{traceback.format_exc()}", file=sys.stderr)
        except Exception:
            pass


class HttpHook(Hook):
    """HTTP hook using urllib (no external deps).

    Config:
    - base_url: str – base URL for events.
    - headers: dict – optional default headers.
    - timeout: float – request timeout.
    - paths: dict – optional mapping to customize endpoints per event name
      (pipeline_start, pipeline_end, step_start, step_end, error).

    Body is JSON: {"event": <name>, "payload": {...}}.
    """

    def __init__(self, base_url: str, headers: Optional[Dict[str, str]] = None, timeout: Optional[float] = 10.0, paths: Optional[Dict[str, str]] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {"Content-Type": "application/json"}
        self.timeout = timeout or 10.0
        self.paths = paths or {}

    # Event callbacks
    def on_pipeline_start(self, pipeline: Any, context: Optional[Dict[str, Any]] = None) -> None:
        payload = {"runners": len(getattr(pipeline, "runners", []))}
        self._post("pipeline_start", payload)

    def on_pipeline_end(self, pipeline: Any, results: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
        self._post("pipeline_end", {"results": results})

    def on_step_start(self, step: Any, context: Optional[Dict[str, Any]] = None) -> None:
        self._post("step_start", {"id": getattr(step, "id", None)})

    def on_step_end(self, step: Any, result: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
        self._post("step_end", {"id": getattr(step, "id", None), "result": result})

    def on_error(self, scope: str, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        self._post("error", {"scope": scope, "error": str(error)})

    # Internal
    def _post(self, event: str, payload: Dict[str, Any]) -> None:
        try:
            import urllib.parse

            path = self.paths.get(event, f"/{event}")
            url = self.base_url + path
            body = json.dumps({"event": event, "payload": payload}).encode("utf-8")
            req = urllib.request.Request(url=url, data=body, headers=self.headers, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout) as _:
                pass
        except Exception:
            # Swallow errors to keep pipeline resilient
            return None
