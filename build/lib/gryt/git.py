from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional


class Git(ABC):
    """Abstract Git client."""
    @abstractmethod
    def clone(self, url: str, path: str) -> bytes|None:
        """Clone a repository."""

    def checkout(self, path: str, ref: str) -> bytes|None:
        """Checkout a ref"""

    def pull(self, path: str) -> bytes|None:
        """Pull the latest changes."""

    def add(self, path: str) -> bytes|None:
        """Stage a file for commit."""

    def commit(self, path: str, message: str) -> bytes|None:
        """Commit changes."""

    def push(self, path: str, args: List[str]) -> bytes|None:
        """Push changes."""

class GitClient(Git):
    """Git client using git command line."""
    def clone(self, url: str, path: str) -> bytes|None:
        """Clone a repository."""
        from subprocess import run
        output = run(["git", "clone", url, path])

        if output.returncode != 0:
            raise Exception(output.stderr.decode("utf-8"))
        else:
            return output.stdout

    def checkout(self, path: str, ref: str) -> bytes|None:
        """Checkout a ref"""
        from subprocess import run
        output = run(["git", "checkout", ref], cwd=path)

        if output.returncode != 0:
            raise Exception(output.stderr.decode("utf-8"))
        else:
            return output.stdout

    def pull(self, path: str) -> bytes|None:
        """Pull the latest changes."""
        from subprocess import run
        output = run(["git", "pull"], cwd=path)

        if output.returncode != 0:
            raise Exception(output.stderr.decode("utf-8"))
        else:
            return output.stdout

    def add(self, path: str) -> bytes|None:
        """Stage a file for commit."""
        from subprocess import run
        output = run(["git", "add", path])

        if output.returncode != 0:
            raise Exception(output.stderr.decode("utf-8"))
        else:
            return output.stdout

    def commit(self, path: str, message: str) -> bytes|None:
        """Commit changes."""
        from subprocess import run
        output = run(["git", "commit", "-m", message], cwd=path)

        if output.returncode != 0:
            raise Exception(output.stderr.decode("utf-8"))
        else:
            return output.stdout

    def push(self, path: str, args: Optional[List[str]]) -> bytes:
        """Push changes."""
        from subprocess import run
        output = run(["git", "push", [f"{x}" for x in args]], cwd=path, capture_output=True)

        if output.returncode != 0:
            raise Exception(output.stderr.decode("utf-8"))
        else:
            return output.stdout