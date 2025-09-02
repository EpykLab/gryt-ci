from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class EnvIssue:
    kind: str         # 'env_var_missing' | 'tool_missing' | 'tool_version'
    name: str         # variable or tool name
    message: str
    details: Optional[Dict[str, Any]] = None


class EnvValidator:
    """Base class for environment validators that collect issues without raising."""

    def run(self) -> List[EnvIssue]:
        raise NotImplementedError


class EnvVarValidator(EnvValidator):
    """Validate required environment variables are present and non-empty."""
    def __init__(self, required: List[str]) -> None:
        self.required = list(required)

    def run(self) -> List[EnvIssue]:
        import os
        issues: List[EnvIssue] = []
        for var in self.required:
            val = os.environ.get(var)
            if val is None or (isinstance(val, str) and val.strip() == ""):
                issues.append(EnvIssue(kind="env_var_missing", name=var, message=f"Environment variable {var} is required"))
        return issues


class ToolValidator(EnvValidator):
    """Validate required CLI tools exist and optionally meet minimum version.

    Each item in tools should be a dict with:
      - name: str (executable name)
      - min_version: str (optional, e.g. '1.0.0')
      - version_args: List[str] (optional override, default: ['--version'])
      - version_regex: str (optional regex to extract version, default: first x.y.z-like token)
    """

    def __init__(self, tools: List[Dict[str, Any]]) -> None:
        self.tools = tools

    def _parse_version(self, text: str, pattern: Optional[str]) -> Optional[str]:
        if pattern:
            m = re.search(pattern, text)
            return m.group(1) if m else None
        # Fallback: first token that looks like 1.2 or 1.2.3
        m = re.search(r"\b(\d+\.\d+(?:\.\d+)*)\b", text)
        return m.group(1) if m else None

    def _version_tuple(self, s: str) -> List[int]:
        return [int(p) for p in re.split(r"[._-]", s) if p.isdigit()]

    def run(self) -> List[EnvIssue]:
        issues: List[EnvIssue] = []
        for t in self.tools:
            name = t.get("name")
            if not name:
                continue
            exe = shutil.which(name)
            if not exe:
                issues.append(EnvIssue(kind="tool_missing", name=name, message=f"Required tool '{name}' not found on PATH"))
                continue
            minv = t.get("min_version")
            if minv:
                args = t.get("version_args") or ["--version"]
                try:
                    cp = subprocess.run([exe] + args, capture_output=True, text=True, check=False)
                    out = (cp.stdout or "") + "\n" + (cp.stderr or "")
                    found = self._parse_version(out, t.get("version_regex"))
                    if not found or self._version_tuple(found) < self._version_tuple(minv):
                        issues.append(
                            EnvIssue(
                                kind="tool_version",
                                name=name,
                                message=f"Tool '{name}' version {found or 'unknown'} is below required {minv}",
                                details={"found": found, "required": minv},
                            )
                        )
                except Exception as e:  # noqa: BLE001
                    issues.append(EnvIssue(kind="tool_version", name=name, message=f"Failed to check version for '{name}': {e}"))
        return issues
