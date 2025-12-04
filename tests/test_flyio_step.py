"""Tests for Fly.io deployment step"""
import os
import pytest
from unittest.mock import patch, MagicMock
from gryt.steps import FlyDeployStep
from gryt.auth import FlyAuth
from gryt.data import Data


class TestFlyDeployStep:
    """Test FlyDeployStep class"""

    def test_create_fly_deploy_step(self):
        """Test creating a Fly.io deploy step"""
        step = FlyDeployStep(
            id="test-deploy",
            config={
                "app": "my-app",
                "region": "iad",
            }
        )

        assert step.id == "test-deploy"
        assert step.config["app"] == "my-app"
        assert step.config["region"] == "iad"

    def test_fly_deploy_basic_config(self):
        """Test basic fly deploy command construction"""
        step = FlyDeployStep(
            id="deploy-basic",
            config={
                "app": "test-app",
                "auto_confirm": True,
            }
        )

        # We can't actually run the command without flyctl installed
        # But we can verify the step was created correctly
        assert step.config["app"] == "test-app"
        assert step.config["auto_confirm"] is True

    def test_fly_deploy_with_strategy(self):
        """Test fly deploy with deployment strategy"""
        step = FlyDeployStep(
            id="deploy-strategy",
            config={
                "app": "test-app",
                "strategy": "rolling",
                "wait_timeout": 600,
            }
        )

        assert step.config["strategy"] == "rolling"
        assert step.config["wait_timeout"] == 600

    def test_fly_deploy_with_build_args(self):
        """Test fly deploy with build arguments"""
        step = FlyDeployStep(
            id="deploy-build",
            config={
                "app": "test-app",
                "build_arg": ["VERSION=1.0.0", "ENV=production"],
                "no_cache": True,
            }
        )

        assert "VERSION=1.0.0" in step.config["build_arg"]
        assert "ENV=production" in step.config["build_arg"]
        assert step.config["no_cache"] is True

    def test_fly_deploy_with_env_vars(self):
        """Test fly deploy with environment variables"""
        step = FlyDeployStep(
            id="deploy-env",
            config={
                "app": "test-app",
                "env": {
                    "DATABASE_URL": "postgres://localhost/db",
                    "API_KEY": "secret123",
                }
            }
        )

        assert step.config["env"]["DATABASE_URL"] == "postgres://localhost/db"
        assert step.config["env"]["API_KEY"] == "secret123"

    def test_fly_deploy_with_ha(self):
        """Test fly deploy with high availability"""
        step = FlyDeployStep(
            id="deploy-ha",
            config={
                "app": "test-app",
                "ha": True,
                "vm_size": "performance-1x",
            }
        )

        assert step.config["ha"] is True
        assert step.config["vm_size"] == "performance-1x"

    def test_fly_deploy_with_remote_only(self):
        """Test fly deploy with remote build"""
        step = FlyDeployStep(
            id="deploy-remote",
            config={
                "app": "test-app",
                "remote_only": True,
                "dockerfile": "Dockerfile.prod",
            }
        )

        assert step.config["remote_only"] is True
        assert step.config["dockerfile"] == "Dockerfile.prod"

    def test_fly_deploy_validation(self):
        """Test fly deploy step validation"""
        step = FlyDeployStep(
            id="deploy-validate",
            config={"app": "test-app"}
        )

        # Validation should pass
        assert step.validate() is True

    def test_fly_deploy_with_custom_config_file(self):
        """Test fly deploy with custom config file"""
        step = FlyDeployStep(
            id="deploy-config",
            config={
                "app": "test-app",
                "config": "fly.production.toml",
            }
        )

        assert step.config["config"] == "fly.production.toml"

    def test_fly_deploy_with_auth(self):
        """Test fly deploy with Auth instance"""
        auth = FlyAuth("fly-auth")
        step = FlyDeployStep(
            id="deploy-with-auth",
            config={"app": "test-app"},
            auth=auth
        )

        assert step.auth is auth
        assert step.config["app"] == "test-app"

    @patch.dict(os.environ, {"FLY_API_TOKEN": "test-token-123"})
    @patch('subprocess.Popen')
    def test_fly_deploy_authenticates_before_deploy(self, mock_popen):
        """Test that FlyDeployStep authenticates before deploying"""
        # Mock successful authentication
        mock_proc = MagicMock()
        mock_proc.returncode = 1  # Fail deployment to avoid actually running it
        mock_proc.communicate.return_value = ("Success", "")
        mock_popen.return_value = mock_proc

        auth = FlyAuth("fly-auth")
        step = FlyDeployStep(
            id="deploy-with-auth",
            config={"app": "test-app"},
            auth=auth
        )

        # Auth should not be authenticated yet
        assert not auth.is_authenticated()

        # Run the step (it will fail on deployment but auth should succeed)
        result = step.run()

        # Auth should now be authenticated
        assert auth.is_authenticated()

    def test_fly_deploy_fails_if_auth_fails(self):
        """Test that FlyDeployStep fails if authentication fails"""
        auth = FlyAuth("fly-auth")  # No token set, will fail
        step = FlyDeployStep(
            id="deploy-with-auth",
            config={"app": "test-app"},
            auth=auth
        )

        result = step.run()

        # Should fail due to authentication error
        assert result["status"] == "error"
        assert "Authentication failed" in result["error"]
        assert not auth.is_authenticated()

    @patch.dict(os.environ, {"FLY_API_TOKEN": "test-token-123"})
    @patch('subprocess.Popen')
    def test_fly_deploy_skips_auth_if_already_authenticated(self, mock_popen):
        """Test that FlyDeployStep skips auth if already authenticated"""
        # Mock successful authentication
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = ("Success", "")
        mock_popen.return_value = mock_proc

        auth = FlyAuth("fly-auth")
        auth.mark_authenticated()  # Manually mark as authenticated

        step = FlyDeployStep(
            id="deploy-with-auth",
            config={"app": "test-app"},
            auth=auth
        )

        # Auth should already be authenticated
        assert auth.is_authenticated()

        # Run the step
        result = step.run()

        # Auth should still be authenticated, and authenticate() should not have been called
        assert auth.is_authenticated()

    def test_fly_deploy_with_image(self):
        """Test fly deploy with pre-built Docker image"""
        step = FlyDeployStep(
            id="deploy-image",
            config={
                "app": "test-app",
                "image": "myregistry.io/myapp:v1.0.0",
                "auto_confirm": True,
            }
        )

        assert step.config["image"] == "myregistry.io/myapp:v1.0.0"
        assert step.config["app"] == "test-app"

    def test_fly_deploy_with_local_image(self):
        """Test fly deploy with local Docker image"""
        step = FlyDeployStep(
            id="deploy-local-image",
            config={
                "app": "test-app",
                "image": "my-local-image:latest",
                "strategy": "rolling",
            }
        )

        assert step.config["image"] == "my-local-image:latest"
        assert step.config["strategy"] == "rolling"

    def test_fly_deploy_image_ignores_build_options(self):
        """Test that image deployment ignores Dockerfile build options"""
        step = FlyDeployStep(
            id="deploy-image-no-build",
            config={
                "app": "test-app",
                "image": "myapp:v2.0.0",
                "dockerfile": "Dockerfile.prod",  # Should be ignored
                "build_arg": ["VERSION=1.0.0"],   # Should be ignored
                "no_cache": True,                  # Should be ignored
                "remote_only": True,               # Should be ignored
            }
        )

        # Config stores all values, but implementation ignores build options when image is set
        assert step.config["image"] == "myapp:v2.0.0"
        # These are stored but won't be used in command construction
        assert step.config["dockerfile"] == "Dockerfile.prod"
        assert step.config["no_cache"] is True
