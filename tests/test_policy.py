"""Tests for Policy and Hooks (v0.5.0)"""
import pytest
from pathlib import Path
import yaml
from gryt.policy import Policy, PolicySet, PolicyViolation
from gryt.hook import PolicyHook, ChangeTypeHook
from gryt.generation import Generation, GenerationChange


class TestPolicy:
    """Test Policy class"""

    def test_create_policy(self):
        """Test creating a policy"""
        policy = Policy(
            name="test_policy",
            policy_type="change_type",
            enabled=True,
            config={"change_types": ["add"], "required_steps": ["test"]}
        )

        assert policy.name == "test_policy"
        assert policy.type == "change_type"
        assert policy.enabled is True

    def test_applies_to(self):
        """Test policy applies_to logic"""
        policy = Policy(
            name="add_only",
            policy_type="change_type",
            config={"change_types": ["add"]}
        )

        assert policy.applies_to("add") is True
        assert policy.applies_to("fix") is False

    def test_validate_change_type_success(self, test_db):
        """Test change type validation passes"""
        policy = Policy(
            name="require_tests",
            policy_type="change_type",
            config={
                "change_types": ["add"],
                "required_steps": ["test", "lint"]
            }
        )

        gen = Generation(
            version="v1.0.0",
            changes=[GenerationChange("CH-001", "add", "Feature")]
        )
        gen.save_to_db(test_db)

        # Should not raise
        policy.validate(
            "add",
            "CH-001",
            gen.generation_id,
            test_db,
            pipeline_steps=["test", "lint", "build"]
        )

    def test_validate_change_type_failure(self, test_db):
        """Test change type validation fails"""
        policy = Policy(
            name="require_e2e",
            policy_type="change_type",
            config={
                "change_types": ["add"],
                "required_steps": ["e2e_test"]
            }
        )

        gen = Generation(
            version="v2.0.0",
            changes=[GenerationChange("CH-002", "add", "Feature")]
        )
        gen.save_to_db(test_db)

        with pytest.raises(PolicyViolation) as exc_info:
            policy.validate(
                "add",
                "CH-002",
                gen.generation_id,
                test_db,
                pipeline_steps=["test", "lint"]
            )

        assert "e2e_test" in str(exc_info.value)

    def test_to_dict(self):
        """Test policy serialization"""
        policy = Policy(
            name="test",
            policy_type="change_type",
            enabled=False,
            config={"foo": "bar"}
        )

        data = policy.to_dict()

        assert data["name"] == "test"
        assert data["type"] == "change_type"
        assert data["enabled"] is False
        assert data["config"]["foo"] == "bar"

    def test_from_dict(self):
        """Test policy deserialization"""
        data = {
            "name": "test",
            "type": "change_type",
            "enabled": True,
            "config": {"key": "value"}
        }

        policy = Policy.from_dict(data)

        assert policy.name == "test"
        assert policy.type == "change_type"
        assert policy.enabled is True


class TestPolicySet:
    """Test PolicySet class"""

    def test_from_yaml_file(self, temp_dir):
        """Test loading policy set from YAML"""
        yaml_path = temp_dir / "policies.yaml"
        yaml_content = {
            "policies": [
                {
                    "name": "require_tests",
                    "type": "change_type",
                    "enabled": True,
                    "config": {
                        "change_types": ["add"],
                        "required_steps": ["test"]
                    }
                }
            ]
        }

        with open(yaml_path, "w") as f:
            yaml.dump(yaml_content, f)

        policy_set = PolicySet.from_yaml_file(yaml_path)

        assert len(policy_set.policies) == 1
        assert policy_set.policies[0].name == "require_tests"

    def test_validate_all(self, test_db, temp_dir):
        """Test validating all policies"""
        policies = [
            Policy(
                name="require_tests",
                policy_type="change_type",
                config={
                    "change_types": ["add"],
                    "required_steps": ["test"]
                }
            ),
            Policy(
                name="require_docs",
                policy_type="change_type",
                config={
                    "change_types": ["add"],
                    "required_steps": ["docs"]
                }
            )
        ]

        policy_set = PolicySet(policies)

        gen = Generation(
            version="v3.0.0",
            changes=[GenerationChange("CH-003", "add", "Feature")]
        )
        gen.save_to_db(test_db)

        # Missing both steps
        violations = policy_set.validate_all(
            "add",
            "CH-003",
            gen.generation_id,
            test_db,
            pipeline_steps=["build"]
        )

        assert len(violations) == 2


class TestPolicyHook:
    """Test PolicyHook class"""

    def test_validate_for_evolution_success(self, test_db):
        """Test policy hook validation passes"""
        policies = [
            Policy(
                name="require_tests",
                policy_type="change_type",
                config={
                    "change_types": ["add"],
                    "required_steps": ["test"]
                }
            )
        ]

        policy_set = PolicySet(policies)
        hook = PolicyHook(policy_set)

        gen = Generation(
            version="v4.0.0",
            changes=[GenerationChange("CH-004", "add", "Feature")]
        )
        gen.save_to_db(test_db)

        # Should not raise
        hook.validate_for_evolution(
            "add",
            "CH-004",
            gen.generation_id,
            test_db,
            pipeline_steps=["test", "build"]
        )

    def test_validate_for_evolution_failure(self, test_db):
        """Test policy hook validation fails"""
        policies = [
            Policy(
                name="require_security",
                policy_type="change_type",
                config={
                    "change_types": ["fix"],
                    "required_steps": ["security_scan"]
                }
            )
        ]

        policy_set = PolicySet(policies)
        hook = PolicyHook(policy_set)

        gen = Generation(
            version="v5.0.0",
            changes=[GenerationChange("CH-005", "fix", "Bug fix")]
        )
        gen.save_to_db(test_db)

        with pytest.raises(PolicyViolation):
            hook.validate_for_evolution(
                "fix",
                "CH-005",
                gen.generation_id,
                test_db,
                pipeline_steps=["test"]
            )


class TestChangeTypeHook:
    """Test ChangeTypeHook class"""

    def test_on_add_callback(self):
        """Test on_add callback is invoked"""
        called = []

        def on_add(change, context):
            called.append(("add", change, context))

        hook = ChangeTypeHook(on_add=on_add)
        hook.on_change_type_add("test_change", {"key": "value"})

        assert len(called) == 1
        assert called[0][0] == "add"
        assert called[0][1] == "test_change"

    def test_multiple_callbacks(self):
        """Test multiple change type callbacks"""
        calls = []

        def on_add(change, context):
            calls.append("add")

        def on_fix(change, context):
            calls.append("fix")

        hook = ChangeTypeHook(on_add=on_add, on_fix=on_fix)

        hook.on_change_type_add("change1", None)
        hook.on_change_type_fix("change2", None)

        assert calls == ["add", "fix"]

    def test_callback_exception_handling(self):
        """Test callbacks handle exceptions gracefully"""
        def failing_callback(change, context):
            raise ValueError("Test error")

        hook = ChangeTypeHook(on_add=failing_callback)

        # Should not raise
        hook.on_change_type_add("change", None)
