from __future__ import annotations

import re
import subprocess
from abc import ABC, abstractmethod
from typing import Optional


SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


class Versioning(ABC):
    """Abstract versioning provider."""

    @abstractmethod
    def bump_version(self, level: str = "patch") -> str:
        """Bump semantic version and return new version string."""

    @abstractmethod
    def tag_release(self, version: str, message: str) -> None:
        """Create a git tag for the version."""


class SimpleVersioning(Versioning):
    """Simplistic git-based semver bump using latest tag.

    - Reads last tag via `git describe --tags --abbrev=0` (defaults to 0.0.0 if none).
    - Bumps major/minor/patch.
    - Does not push or write files; only returns string and can create a tag.
    """

    def _get_last_tag(self) -> str:
        try:
            out = subprocess.check_output(["git", "describe", "--tags", "--abbrev=0"], text=True).strip()
            if out:
                return out
        except Exception:
            pass
        return "0.0.0"

    def bump_version(self, level: str = "patch") -> str:
        last = self._get_last_tag()
        m = SEMVER_RE.match(last)
        if not m:
            # If last tag is non-semver, reset to 0.0.0
            major, minor, patch = 0, 0, 0
        else:
            major, minor, patch = map(int, m.groups())
        if level == "major":
            major += 1
            minor = 0
            patch = 0
        elif level == "minor":
            minor += 1
            patch = 0
        else:
            patch += 1
        return f"{major}.{minor}.{patch}"

    def tag_release(self, version: str, message: str) -> None:
        subprocess.check_call(["git", "tag", "-a", version, "-m", message])
