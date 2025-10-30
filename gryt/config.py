"""Configuration management for Gryt CLI."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional
import yaml


GLOBAL_CONFIG_PATH = Path.home() / ".gryt.yaml"


class Config:
    """Manages Gryt configuration with hierarchical lookup.

    Config hierarchy (higher priority first):
    1. Local repo config (.gryt/config)
    2. Global config (~/.gryt.yaml)

    When reading, local values override global.
    When writing, writes to the config path specified at init (local or global).
    """

    def __init__(self, config_path: Optional[Path] = None, enable_hierarchy: bool = True):
        """Initialize config.

        Args:
            config_path: Specific config file to use. If None, uses global config.
            enable_hierarchy: If True, uses hierarchical lookup (local + global).
                             If False, only uses the specified config_path.
        """
        self.config_path = config_path or GLOBAL_CONFIG_PATH
        self.enable_hierarchy = enable_hierarchy
        self._data: dict[str, Any] = {}
        self._global_data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Load configuration from file(s)."""
        # Load primary config
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    self._data = yaml.safe_load(f) or {}
            except Exception as e:
                raise RuntimeError(f"Failed to load config from {self.config_path}: {e}") from e
        else:
            self._data = {}

        # Load global config for hierarchy (if enabled and we're not already loading global)
        if self.enable_hierarchy and self.config_path != GLOBAL_CONFIG_PATH:
            if GLOBAL_CONFIG_PATH.exists():
                try:
                    with open(GLOBAL_CONFIG_PATH) as f:
                        self._global_data = yaml.safe_load(f) or {}
                except Exception:
                    self._global_data = {}
            else:
                self._global_data = {}
        else:
            self._global_data = {}

    def save(self) -> None:
        """Save configuration to primary config file."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w") as f:
                yaml.dump(self._data, f, default_flow_style=False)
        except Exception as e:
            raise RuntimeError(f"Failed to save config to {self.config_path}: {e}") from e

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value with hierarchical lookup.

        Checks local config first, then global, then returns default.
        """
        # Check local config first
        if key in self._data:
            return self._data[key]

        # Fall back to global config
        if key in self._global_data:
            return self._global_data[key]

        return default

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value in the primary config."""
        self._data[key] = value

    def copy_from_global(self) -> None:
        """Copy all values from global config to local config.

        Only copies keys that don't already exist in local config.
        Useful when initializing a new repo config.
        """
        for key, value in self._global_data.items():
            if key not in self._data:
                self._data[key] = value

    @property
    def username(self) -> Optional[str]:
        """Get configured username."""
        return self.get("username")

    @username.setter
    def username(self, value: str) -> None:
        self.set("username", value)

    @property
    def password(self) -> Optional[str]:
        """Get configured password."""
        return self.get("password")

    @password.setter
    def password(self, value: str) -> None:
        self.set("password", value)

    @property
    def api_key_id(self) -> Optional[str]:
        """Get configured API key ID."""
        return self.get("api_key_id")

    @api_key_id.setter
    def api_key_id(self, value: str) -> None:
        self.set("api_key_id", value)

    @property
    def api_key_secret(self) -> Optional[str]:
        """Get configured API key secret."""
        return self.get("api_key_secret")

    @api_key_secret.setter
    def api_key_secret(self, value: str) -> None:
        self.set("api_key_secret", value)

    @property
    def gryt_url(self) -> Optional[str]:
        """Get configured Gryt URL."""
        return self.get("gryt_url")

    @gryt_url.setter
    def gryt_url(self, value: str) -> None:
        self.set("gryt_url", value)

    @property
    def execution_mode(self) -> str:
        """Get execution mode (local, cloud, hybrid)."""
        return self.get("execution_mode", "hybrid")

    @execution_mode.setter
    def execution_mode(self, value: str) -> None:
        self.set("execution_mode", value)

    def has_credentials(self) -> bool:
        """Check if credentials are configured."""
        has_basic = bool(self.username and self.password)
        has_api_key = bool(self.api_key_id and self.api_key_secret)
        return has_basic or has_api_key

    @classmethod
    def load_with_repo_context(cls, start_path: Optional[Path] = None) -> Config:
        """Load config with repo context if available.

        Tries to find repo-local config first, falls back to global.
        Uses hierarchical lookup so local overrides global.

        Args:
            start_path: Starting directory for repo search

        Returns:
            Config instance with hierarchical lookup enabled
        """
        from .paths import get_repo_config_path

        repo_config_path = get_repo_config_path(start_path)
        if repo_config_path:
            # In a repo - use local config with global fallback
            return cls(config_path=repo_config_path, enable_hierarchy=True)
        else:
            # Not in a repo - use global config only
            return cls(config_path=GLOBAL_CONFIG_PATH, enable_hierarchy=False)
