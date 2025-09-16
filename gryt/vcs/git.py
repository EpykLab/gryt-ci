from __future__ import annotations

from .. import Data, Hook
from ..step import CommandStep
from typing import Any, Dict, List, Optional

class GitClone(CommandStep):
    def __init__(
        self,
        id: str,
        url: str,
        path: str,
        config: Optional[Dict[str, Any]] = None,
        data: Optional[Data] = None,
        hook: Optional["Hook"] = None,
    ) -> None:
        config = config or {}
        config["cmd"] = ["git", "clone", url, path]
        super().__init__(id, config, data, hook)

class GitCheckout(CommandStep):
    def __init__(
        self,
        id: str,
        repo_path: str,
        ref: str,
        config: Optional[Dict[str, Any]] = None,
        data: Optional[Data] = None,
        hook: Optional["Hook"] = None,
    ) -> None:
        config = config or {}
        config["cmd"] = ["git", "checkout", ref]
        config["cwd"] = repo_path
        super().__init__(id, config, data, hook)

class GitPull(CommandStep):
    def __init__(
        self,
        id: str,
        repo_path: str,
        config: Optional[Dict[str, Any]] = None,
        data: Optional[Data] = None,
        hook: Optional["Hook"] = None,
    ) -> None:
        config = config or {}
        config["cmd"] = ["git", "pull"]
        config["cwd"] = repo_path
        super().__init__(id, config, data, hook)

class GitAdd(CommandStep):
    def __init__(
        self,
        id: str,
        file_path: str,
        config: Optional[Dict[str, Any]] = None,
        data: Optional[Data] = None,
        hook: Optional["Hook"] = None,
    ) -> None:
        config = config or {}
        config["cmd"] = ["git", "add", file_path]
        super().__init__(id, config, data, hook)

class GitCommit(CommandStep):
    def __init__(
        self,
        id: str,
        repo_path: str,
        message: str,
        config: Optional[Dict[str, Any]] = None,
        data: Optional[Data] = None,
        hook: Optional["Hook"] = None,
    ) -> None:
        config = config or {}
        config["cmd"] = ["git", "commit", "-m", message]
        config["cwd"] = repo_path
        super().__init__(id, config, data, hook)

class GitPush(CommandStep):
    def __init__(
        self,
        id: str,
        repo_path: str,
        args: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
        data: Optional[Data] = None,
        hook: Optional["Hook"] = None,
    ) -> None:
        config = config or {}
        config["cmd"] = ["git", "push"] + (args or [])
        config["cwd"] = repo_path
        super().__init__(id, config, data, hook)