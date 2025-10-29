"""Configuration management for Gryt CLI."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional
import yaml


DEFAULT_CONFIG_PATH = Path.home() / ".gryt.yaml"


class Config:
    """Manages Gryt configuration from ~/.gryt.yaml"""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self._data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Load configuration from file."""
        if not self.config_path.exists():
            self._data = {}
            return
        try:
            with open(self.config_path) as f:
                self._data = yaml.safe_load(f) or {}
        except Exception as e:
            raise RuntimeError(f"Failed to load config from {self.config_path}: {e}") from e

    def save(self) -> None:
        """Save configuration to file."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w") as f:
                yaml.dump(self._data, f, default_flow_style=False)
        except Exception as e:
            raise RuntimeError(f"Failed to save config to {self.config_path}: {e}") from e

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        self._data[key] = value

    @property
    def username(self) -> Optional[str]:
        """Get configured username."""
        return self._data.get("username")

    @property
    def password(self) -> Optional[str]:
        """Get configured password."""
        return self._data.get("password")

    @property
    def api_key_id(self) -> Optional[str]:
        """Get configured API key ID."""
        return self._data.get("api_key_id")

    @property
    def api_key_secret(self) -> Optional[str]:
        """Get configured API key secret."""
        return self._data.get("api_key_secret")

    @property
    def gryt_url(self) -> Optional[str]:
        """Get configured Gryt URL."""
        return self._data.get("gryt_url")

    @property
    def execution_mode(self) -> str:
        """Get execution mode (local, cloud, hybrid)."""
        return self._data.get("execution_mode", "hybrid")

    def has_credentials(self) -> bool:
        """Check if credentials are configured."""
        has_basic = bool(self.username and self.password)
        has_api_key = bool(self.api_key_id and self.api_key_secret)
        return has_basic or has_api_key
