"""Tests for Config hierarchy and paths module"""
import pytest
from pathlib import Path
from gryt.config import Config, GLOBAL_CONFIG_PATH
from gryt.paths import find_repo_root, get_repo_gryt_dir, get_repo_config_path, get_repo_db_path


class TestRepoRootFinder:
    """Test find_repo_root() function"""

    def test_find_repo_root_in_repo_root(self, gryt_project):
        """Test finding repo root when at the root"""
        root = find_repo_root(gryt_project)
        assert root == gryt_project

    def test_find_repo_root_from_subdirectory(self, gryt_project):
        """Test finding repo root from a subdirectory"""
        # Create subdirectories
        subdir = gryt_project / "src" / "foo" / "bar"
        subdir.mkdir(parents=True)

        # Should find repo root from deep subdirectory
        root = find_repo_root(subdir)
        assert root == gryt_project

    def test_find_repo_root_no_gryt_folder(self, temp_dir):
        """Test when not in a gryt repo"""
        # temp_dir has no .gryt folder
        root = find_repo_root(temp_dir)
        assert root is None

    def test_find_repo_root_requires_git_folder(self, temp_dir):
        """Test that .gryt requires .git at same level"""
        # Create .gryt but no .git
        (temp_dir / ".gryt").mkdir()

        root = find_repo_root(temp_dir)
        # Should not find root since .git is missing
        assert root is None

    def test_get_repo_gryt_dir(self, gryt_project):
        """Test getting .gryt directory path"""
        gryt_dir = get_repo_gryt_dir(gryt_project)
        assert gryt_dir == gryt_project / ".gryt"
        assert gryt_dir.exists()

    def test_get_repo_config_path(self, gryt_project):
        """Test getting repo config path"""
        config_path = get_repo_config_path(gryt_project)
        assert config_path == gryt_project / ".gryt" / "config"

    def test_get_repo_db_path(self, gryt_project):
        """Test getting repo database path"""
        db_path = get_repo_db_path(gryt_project)
        assert db_path == gryt_project / ".gryt" / "gryt.db"


class TestConfigHierarchy:
    """Test Config with hierarchical lookup"""

    def test_config_reads_global(self, temp_dir):
        """Test config reads from global config"""
        # Create a global config with test values
        global_config = Config(config_path=temp_dir / "global.yaml", enable_hierarchy=False)
        global_config.set("username", "global_user")
        global_config.set("api_key_id", "global_key")
        global_config.save()

        # Load it and verify
        loaded = Config(config_path=temp_dir / "global.yaml", enable_hierarchy=False)
        assert loaded.username == "global_user"
        assert loaded.api_key_id == "global_key"

    def test_config_hierarchy_local_overrides_global(self, temp_dir):
        """Test that local config values override global"""
        # Create global config
        global_config_path = temp_dir / "global.yaml"
        global_config = Config(config_path=global_config_path, enable_hierarchy=False)
        global_config.set("username", "global_user")
        global_config.set("api_key_id", "global_key")
        global_config.set("gryt_url", "https://global.example.com")
        global_config.save()

        # Create local config
        local_config_path = temp_dir / "local.yaml"
        local_config = Config(config_path=local_config_path, enable_hierarchy=False)
        local_config.set("username", "local_user")  # Override username
        # api_key_id not set in local
        local_config.save()

        # Now load with hierarchy (simulate GLOBAL_CONFIG_PATH)
        # Need to manually set up hierarchy for test
        config = Config(config_path=local_config_path, enable_hierarchy=False)
        config.load()
        # Manually load global for hierarchy
        config._global_data = global_config._data

        # Local value overrides
        assert config.get("username") == "local_user"
        # Global value used as fallback
        assert config.get("api_key_id") == "global_key"
        assert config.get("gryt_url") == "https://global.example.com"

    def test_config_copy_from_global(self, temp_dir):
        """Test copying global config to local"""
        # Create global config
        global_config_path = temp_dir / "global.yaml"
        global_config = Config(config_path=global_config_path, enable_hierarchy=False)
        global_config.set("username", "global_user")
        global_config.set("api_key_id", "global_key")
        global_config.set("execution_mode", "hybrid")
        global_config.save()

        # Create local config
        local_config_path = temp_dir / "local.yaml"
        local_config = Config(config_path=local_config_path, enable_hierarchy=False)
        local_config._global_data = global_config._data

        # Copy from global
        local_config.copy_from_global()

        # Verify values copied
        assert local_config.get("username") == "global_user"
        assert local_config.get("api_key_id") == "global_key"
        assert local_config.get("execution_mode") == "hybrid"

    def test_config_copy_from_global_doesnt_override_existing(self, temp_dir):
        """Test that copy_from_global doesn't override existing local values"""
        # Create global config
        global_config_path = temp_dir / "global.yaml"
        global_config = Config(config_path=global_config_path, enable_hierarchy=False)
        global_config.set("username", "global_user")
        global_config.set("api_key_id", "global_key")
        global_config.save()

        # Create local config with existing value
        local_config_path = temp_dir / "local.yaml"
        local_config = Config(config_path=local_config_path, enable_hierarchy=False)
        local_config.set("username", "local_user")
        local_config._global_data = global_config._data

        # Copy from global
        local_config.copy_from_global()

        # Local value should not be overridden
        assert local_config.get("username") == "local_user"
        # New value should be copied
        assert local_config.get("api_key_id") == "global_key"

    def test_config_setters_work(self, temp_dir):
        """Test that config property setters work"""
        config_path = temp_dir / "test.yaml"
        config = Config(config_path=config_path, enable_hierarchy=False)

        # Test setters
        config.username = "test_user"
        config.password = "test_pass"
        config.api_key_id = "key_123"
        config.api_key_secret = "secret_456"
        config.gryt_url = "https://test.example.com"
        config.execution_mode = "cloud"

        # Verify getters work
        assert config.username == "test_user"
        assert config.password == "test_pass"
        assert config.api_key_id == "key_123"
        assert config.api_key_secret == "secret_456"
        assert config.gryt_url == "https://test.example.com"
        assert config.execution_mode == "cloud"

        # Save and reload
        config.save()
        loaded = Config(config_path=config_path, enable_hierarchy=False)
        assert loaded.username == "test_user"
        assert loaded.execution_mode == "cloud"


class TestConfigWithRepoContext:
    """Test Config.load_with_repo_context()"""

    def test_load_with_repo_context_in_repo(self, gryt_project):
        """Test loading config when in a repo"""
        # Create local config in repo
        local_config_path = gryt_project / ".gryt" / "config"
        local_config = Config(config_path=local_config_path, enable_hierarchy=False)
        local_config.set("username", "repo_user")
        local_config.save()

        # Load with repo context
        config = Config.load_with_repo_context(start_path=gryt_project)

        # Should load local config
        assert config.config_path == local_config_path
        assert config.enable_hierarchy is True
        assert config.username == "repo_user"

    def test_load_with_repo_context_outside_repo(self, temp_dir):
        """Test loading config when not in a repo"""
        # Not in a repo - should use global config
        config = Config.load_with_repo_context(start_path=temp_dir)

        # Should use global config
        assert config.config_path == GLOBAL_CONFIG_PATH
        assert config.enable_hierarchy is False
