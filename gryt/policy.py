"""
Policy system (v0.5.0)

Policies enforce rules on generation changes and evolutions.
"""
from __future__ import annotations

import json
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional

from .data import SqliteData


class PolicyViolation(Exception):
    """Raised when a policy is violated"""
    def __init__(self, policy_name: str, message: str, details: Optional[Dict[str, Any]] = None):
        self.policy_name = policy_name
        self.message = message
        self.details = details or {}
        super().__init__(f"{policy_name}: {message}")


class Policy:
    """
    A policy that can be enforced on changes and evolutions.

    Attributes:
        name: Policy name
        type: Policy type (change_type, evolution_count, custom)
        enabled: Whether policy is active
        config: Policy-specific configuration
    """

    def __init__(
        self,
        name: str,
        policy_type: str,
        enabled: bool = True,
        config: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.type = policy_type
        self.enabled = enabled
        self.config = config or {}

    def applies_to(self, change_type: str) -> bool:
        """Check if this policy applies to a given change type"""
        if not self.enabled:
            return False

        change_types = self.config.get("change_types", [])
        if not change_types:
            return True  # Applies to all if not specified

        return change_type in change_types

    def validate(
        self,
        change_type: str,
        change_id: str,
        generation_id: str,
        data: SqliteData,
        pipeline_steps: Optional[List[str]] = None
    ) -> None:
        """
        Validate this policy for a change.

        Raises PolicyViolation if validation fails.
        """
        if not self.applies_to(change_type):
            return

        if self.type == "change_type":
            self._validate_change_type(change_type, change_id, pipeline_steps)
        elif self.type == "evolution_count":
            self._validate_evolution_count(change_id, generation_id, data)

    def _validate_change_type(
        self,
        change_type: str,
        change_id: str,
        pipeline_steps: Optional[List[str]]
    ) -> None:
        """Validate change type policies (e.g., require specific steps)"""
        required_steps = self.config.get("required_steps", [])
        if not required_steps:
            return

        if not pipeline_steps:
            raise PolicyViolation(
                self.name,
                f"Required steps {required_steps} not found (no pipeline steps provided)",
                {"required_steps": required_steps, "change_type": change_type}
            )

        missing_steps = [s for s in required_steps if s not in pipeline_steps]
        if missing_steps:
            raise PolicyViolation(
                self.name,
                f"Missing required steps: {', '.join(missing_steps)}",
                {
                    "required_steps": required_steps,
                    "pipeline_steps": pipeline_steps,
                    "missing_steps": missing_steps,
                    "change_type": change_type
                }
            )

    def _validate_evolution_count(
        self,
        change_id: str,
        generation_id: str,
        data: SqliteData
    ) -> None:
        """Validate evolution count policies"""
        min_evolutions = self.config.get("min_evolutions", 1)

        evolutions = data.query(
            """
            SELECT COUNT(*) as count FROM evolutions
            WHERE generation_id = ? AND change_id = ?
            """,
            (generation_id, change_id)
        )

        count = evolutions[0]["count"] if evolutions else 0

        if count < min_evolutions:
            raise PolicyViolation(
                self.name,
                f"Insufficient evolutions: {count}/{min_evolutions}",
                {
                    "min_required": min_evolutions,
                    "actual_count": count,
                    "change_id": change_id
                }
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "type": self.type,
            "enabled": self.enabled,
            "config": self.config
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Policy:
        """Create from dictionary"""
        return cls(
            name=data["name"],
            policy_type=data["type"],
            enabled=data.get("enabled", True),
            config=data.get("config", {})
        )


class PolicySet:
    """
    A collection of policies loaded from configuration.
    """

    def __init__(self, policies: List[Policy]):
        self.policies = policies

    @classmethod
    def from_yaml_file(cls, yaml_path: Path) -> PolicySet:
        """Load policies from YAML file"""
        if not yaml_path.exists():
            return cls([])

        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)

        # Validate against JSON schema
        cls._validate_schema(data)

        policies = [Policy.from_dict(p) for p in data.get("policies", [])]
        return cls(policies)

    def validate_all(
        self,
        change_type: str,
        change_id: str,
        generation_id: str,
        data: SqliteData,
        pipeline_steps: Optional[List[str]] = None
    ) -> List[PolicyViolation]:
        """
        Validate all policies, collecting violations.

        Returns a list of violations (empty if all pass).
        """
        violations = []

        for policy in self.policies:
            try:
                policy.validate(change_type, change_id, generation_id, data, pipeline_steps)
            except PolicyViolation as e:
                violations.append(e)

        return violations

    def get_alerts_config(self) -> Dict[str, Any]:
        """Get alerts configuration from policy file"""
        # This would be loaded from the YAML file
        # For now, return empty config
        return {}

    @staticmethod
    def _validate_schema(data: Dict[str, Any]) -> None:
        """Validate policy YAML against JSON schema"""
        try:
            import jsonschema
        except ImportError:
            return

        schema_path = Path(__file__).parent / "schemas" / "policy.json"
        if not schema_path.exists():
            return

        with open(schema_path, "r") as f:
            schema = json.load(f)

        jsonschema.validate(data, schema)


def get_default_policies() -> List[Policy]:
    """Get a set of sensible default policies"""
    return [
        Policy(
            name="require_e2e_for_add",
            policy_type="change_type",
            enabled=True,
            config={
                "change_types": ["add"],
                "required_steps": ["e2e_test", "integration_test"]
            }
        ),
        Policy(
            name="require_security_scan_for_fix",
            policy_type="change_type",
            enabled=True,
            config={
                "change_types": ["fix"],
                "required_steps": ["security_scan"]
            }
        ),
        Policy(
            name="min_two_evolutions",
            policy_type="evolution_count",
            enabled=False,  # Disabled by default
            config={
                "min_evolutions": 2
            }
        )
    ]
