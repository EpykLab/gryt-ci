from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List


class Runtime(ABC):
    """Abstract runtime environment provisioner."""

    def __init__(self, env_config: Dict[str, List[str]] | None = None) -> None:
        self.env_config = env_config or {}

    @abstractmethod
    def provision(self) -> None:
        """Set up environment (idempotent if possible)."""

    @abstractmethod
    def teardown(self) -> None:
        """Clean up resources (optional)."""


class LocalRuntime(Runtime):
    """Local runtime stub. For MVP, we do not install anything automatically.

    Users can supply commands as Steps to prepare environment.
    """

    def provision(self) -> None:  # noqa: D401 - simple stub
        # Intentionally minimal in MVP
        return None

    def teardown(self) -> None:  # noqa: D401 - simple stub
        # Intentionally minimal in MVP
        return None
