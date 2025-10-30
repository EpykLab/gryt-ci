"""Tests for Promotion Gates (v0.4.0)"""
import pytest
from gryt.generation import Generation, GenerationChange
from gryt.evolution import Evolution
from gryt.gates import (
    AllChangesProvenGate,
    NoFailedEvolutionsGate,
    MinEvolutionsGate,
    get_default_gates
)


class TestAllChangesProvenGate:
    """Test AllChangesProvenGate"""

    def test_passes_when_all_changes_proven(self, test_db):
        """Test gate passes when all changes have PASS evolutions"""
        gen = Generation(
            version="v1.0.0",
            changes=[
                GenerationChange("CH-001", "add", "Feature 1"),
                GenerationChange("CH-002", "fix", "Bug fix")
            ]
        )
        gen.save_to_db(test_db)

        # Create passing evolutions for both changes
        for change in gen.changes:
            evo = Evolution(gen.generation_id, change.change_id, f"v1.0.0-rc.1-{change.change_id}")
            evo.status = "pass"
            evo.save_to_db(test_db)

        gate = AllChangesProvenGate()
        result = gate.check(gen, test_db)

        assert result.passed is True

    def test_fails_when_change_unproven(self, test_db):
        """Test gate fails when a change has no PASS evolution"""
        gen = Generation(
            version="v2.0.0",
            changes=[
                GenerationChange("CH-003", "add", "Feature 1"),
                GenerationChange("CH-004", "fix", "Bug fix")
            ]
        )
        gen.save_to_db(test_db)

        # Only prove one change
        evo = Evolution(gen.generation_id, "CH-003", "v2.0.0-rc.1")
        evo.status = "pass"
        evo.save_to_db(test_db)

        gate = AllChangesProvenGate()
        result = gate.check(gen, test_db)

        assert result.passed is False
        assert "CH-004" in result.message


class TestNoFailedEvolutionsGate:
    """Test NoFailedEvolutionsGate"""

    def test_passes_with_no_failures(self, test_db):
        """Test gate passes when no evolutions have failed"""
        gen = Generation(
            version="v3.0.0",
            changes=[GenerationChange("CH-005", "add", "Feature")]
        )
        gen.save_to_db(test_db)

        # All passing
        for i in range(3):
            evo = Evolution(gen.generation_id, "CH-005", f"v3.0.0-rc.{i+1}")
            evo.status = "pass"
            evo.save_to_db(test_db)

        gate = NoFailedEvolutionsGate()
        result = gate.check(gen, test_db)

        assert result.passed is True

    def test_fails_with_failed_evolutions(self, test_db):
        """Test gate fails when there are failed evolutions"""
        gen = Generation(
            version="v4.0.0",
            changes=[GenerationChange("CH-006", "add", "Feature")]
        )
        gen.save_to_db(test_db)

        # One passing, one failing
        evo1 = Evolution(gen.generation_id, "CH-006", "v4.0.0-rc.1")
        evo1.status = "pass"
        evo1.save_to_db(test_db)

        evo2 = Evolution(gen.generation_id, "CH-006", "v4.0.0-rc.2")
        evo2.status = "fail"
        evo2.save_to_db(test_db)

        gate = NoFailedEvolutionsGate()
        result = gate.check(gen, test_db)

        assert result.passed is False
        assert "Failed evolutions" in result.message or "failed evolution" in result.message


class TestMinEvolutionsGate:
    """Test MinEvolutionsGate"""

    def test_passes_when_minimum_met(self, test_db):
        """Test gate passes when minimum evolutions exist"""
        gen = Generation(
            version="v5.0.0",
            changes=[GenerationChange("CH-007", "add", "Feature")]
        )
        gen.save_to_db(test_db)

        # Create 3 evolutions
        for i in range(3):
            evo = Evolution(gen.generation_id, "CH-007", f"v5.0.0-rc.{i+1}")
            evo.status = "pass"
            evo.save_to_db(test_db)

        gate = MinEvolutionsGate(min_evolutions=2)
        result = gate.check(gen, test_db)

        assert result.passed is True

    def test_fails_when_minimum_not_met(self, test_db):
        """Test gate fails when minimum not reached"""
        gen = Generation(
            version="v6.0.0",
            changes=[GenerationChange("CH-008", "add", "Feature")]
        )
        gen.save_to_db(test_db)

        # Only 1 evolution
        evo = Evolution(gen.generation_id, "CH-008", "v6.0.0-rc.1")
        evo.status = "pass"
        evo.save_to_db(test_db)

        gate = MinEvolutionsGate(min_evolutions=3)
        result = gate.check(gen, test_db)

        assert result.passed is False
        assert "1/3" in result.message


class TestDefaultGates:
    """Test default gate configuration"""

    def test_get_default_gates(self):
        """Test default gates are returned correctly"""
        gates = get_default_gates()

        assert len(gates) >= 2
        assert any(isinstance(g, AllChangesProvenGate) for g in gates)
        assert any(isinstance(g, NoFailedEvolutionsGate) for g in gates)

    def test_default_gates_integration(self, test_db):
        """Test default gates work together"""
        gen = Generation(
            version="v7.0.0",
            changes=[GenerationChange("CH-009", "add", "Feature")]
        )
        gen.save_to_db(test_db)

        # Create passing evolution
        evo = Evolution(gen.generation_id, "CH-009", "v7.0.0-rc.1")
        evo.status = "pass"
        evo.save_to_db(test_db)

        # Run all default gates
        gates = get_default_gates()
        results = []
        for gate in gates:
            result = gate.check(gen, test_db)
            results.append(result)

        # All should pass
        assert all(r.passed for r in results)
