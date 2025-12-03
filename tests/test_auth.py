"""Tests for Auth system"""
import os
import pytest
from unittest.mock import patch, MagicMock
from gryt.auth import Auth, FlyAuth


class TestAuth:
    """Test Auth base class"""

    def test_auth_is_abstract(self):
        """Test that Auth cannot be instantiated directly"""
        with pytest.raises(TypeError):
            Auth("test-auth")

    def test_auth_initialization(self):
        """Test Auth initialization through concrete implementation"""
        auth = FlyAuth("test-auth", {"token_env_var": "TEST_TOKEN"})

        assert auth.id == "test-auth"
        assert auth.config["token_env_var"] == "TEST_TOKEN"
        assert not auth.is_authenticated()

    def test_mark_authenticated(self):
        """Test marking auth as authenticated"""
        auth = FlyAuth("test-auth")

        assert not auth.is_authenticated()
        auth.mark_authenticated()
        assert auth.is_authenticated()


class TestFlyAuth:
    """Test FlyAuth implementation"""

    def test_create_fly_auth(self):
        """Test creating a FlyAuth instance"""
        auth = FlyAuth("fly-auth", {
            "token_env_var": "FLY_API_TOKEN",
            "timeout": 30
        })

        assert auth.id == "fly-auth"
        assert auth.config["token_env_var"] == "FLY_API_TOKEN"
        assert auth.config["timeout"] == 30

    def test_fly_auth_default_token_env_var(self):
        """Test FlyAuth uses default token env var"""
        auth = FlyAuth("fly-auth")
        result = auth.authenticate()

        # Should fail because FLY_API_TOKEN is not set
        assert result["status"] == "error"
        assert "FLY_API_TOKEN" in result["error"]

    def test_fly_auth_custom_token_env_var(self):
        """Test FlyAuth with custom token env var"""
        auth = FlyAuth("fly-auth", {"token_env_var": "CUSTOM_FLY_TOKEN"})
        result = auth.authenticate()

        # Should fail because CUSTOM_FLY_TOKEN is not set
        assert result["status"] == "error"
        assert "CUSTOM_FLY_TOKEN" in result["error"]

    @patch.dict(os.environ, {}, clear=True)
    def test_fly_auth_missing_token(self):
        """Test FlyAuth when token is missing from environment"""
        auth = FlyAuth("fly-auth")
        result = auth.authenticate()

        assert result["status"] == "error"
        assert "FLY_API_TOKEN" in result["error"]
        assert not auth.is_authenticated()

    @patch.dict(os.environ, {"FLY_API_TOKEN": "test-token-123"})
    @patch('subprocess.Popen')
    def test_fly_auth_successful_authentication(self, mock_popen):
        """Test successful FlyAuth authentication"""
        # Mock successful authentication
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = ("Successfully authenticated", "")
        mock_popen.return_value = mock_proc

        auth = FlyAuth("fly-auth")
        result = auth.authenticate()

        assert result["status"] == "success"
        assert "Successfully authenticated" in result["message"]
        assert auth.is_authenticated()

        # Verify the command was called correctly
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        assert call_args[0][0] == ["fly", "auth", "token"]

    @patch.dict(os.environ, {"FLY_API_TOKEN": "test-token-123"})
    @patch('subprocess.Popen')
    def test_fly_auth_failed_authentication(self, mock_popen):
        """Test failed FlyAuth authentication"""
        # Mock failed authentication
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.communicate.return_value = ("", "Authentication failed: invalid token")
        mock_popen.return_value = mock_proc

        auth = FlyAuth("fly-auth")
        result = auth.authenticate()

        assert result["status"] == "error"
        assert "Authentication failed" in result["error"]
        assert not auth.is_authenticated()

    @patch.dict(os.environ, {"FLY_API_TOKEN": "test-token-123"})
    @patch('subprocess.Popen')
    def test_fly_auth_already_authenticated(self, mock_popen):
        """Test that FlyAuth skips authentication if already authenticated"""
        # Mock successful first authentication
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = ("Successfully authenticated", "")
        mock_popen.return_value = mock_proc

        auth = FlyAuth("fly-auth")

        # First authentication
        result1 = auth.authenticate()
        assert result1["status"] == "success"
        assert auth.is_authenticated()

        # Second authentication should skip
        result2 = auth.authenticate()
        assert result2["status"] == "success"
        assert result2.get("skipped") is True
        assert "Already authenticated" in result2["message"]

        # Should only have been called once
        assert mock_popen.call_count == 1

    @patch.dict(os.environ, {"FLY_API_TOKEN": "test-token-123"})
    @patch('subprocess.Popen')
    def test_fly_auth_with_data_tracking(self, mock_popen):
        """Test FlyAuth with data parameter (without actually querying)"""
        # Mock successful authentication
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = ("Successfully authenticated", "")
        mock_popen.return_value = mock_proc

        # Create a mock data object to avoid memory issues
        mock_data = MagicMock()

        auth = FlyAuth("fly-auth", data=mock_data)
        result = auth.authenticate()

        assert result["status"] == "success"

        # Verify that data.insert was called
        mock_data.insert.assert_called_once()
        call_args = mock_data.insert.call_args
        assert call_args[0][0] == "auth_output"
        assert call_args[0][1]["auth_id"] == "fly-auth"
        assert call_args[0][1]["type"] == "FlyAuth"
        assert call_args[0][1]["status"] == "success"

    @patch.dict(os.environ, {"FLY_API_TOKEN": "test-token-123"})
    @patch('subprocess.Popen')
    def test_fly_auth_timeout(self, mock_popen):
        """Test FlyAuth timeout handling"""
        import subprocess

        # Mock timeout
        mock_proc = MagicMock()
        mock_proc.communicate.side_effect = subprocess.TimeoutExpired("fly auth token", 30)
        mock_popen.return_value = mock_proc

        auth = FlyAuth("fly-auth", {"timeout": 30})
        result = auth.authenticate()

        assert result["status"] == "error"
        assert "timed out" in result["error"]
        assert not auth.is_authenticated()

    @patch.dict(os.environ, {"FLY_API_TOKEN": "test-token-123"})
    @patch('subprocess.Popen')
    def test_fly_auth_exception_handling(self, mock_popen):
        """Test FlyAuth handles unexpected exceptions"""
        # Mock exception
        mock_popen.side_effect = Exception("Unexpected error")

        auth = FlyAuth("fly-auth")
        result = auth.authenticate()

        assert result["status"] == "error"
        assert "Unexpected error" in result["error"]
        assert not auth.is_authenticated()
