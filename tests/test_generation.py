"""Tests for Generation and Evolution (v0.2.0, v0.3.0)"""
import pytest
from datetime import datetime
from gryt.generation import Generation, GenerationChange
from gryt.evolution import Evolution


class TestGeneration:
    """Test Generation functionality"""

    def test_create_generation(self, test_db):
        """Test creating a generation"""
        changes = [
            GenerationChange(
                change_id="FEAT-001",
                change_type="add",
                title="Add user authentication",
                description="Implement OAuth2 flow"
            )
        ]

        gen = Generation(
            version="v1.0.0",
            description="Initial release",
            changes=changes
        )

        gen.save_to_db(test_db)

        # Verify in database
        rows = test_db.query(
            "SELECT * FROM generations WHERE version = ?",
            ("v1.0.0",)
        )

        assert len(rows) == 1
        assert rows[0]["version"] == "v1.0.0"
        assert rows[0]["status"] == "draft"

    def test_load_generation_from_db(self, test_db):
        """Test loading generation from database"""
        # Create and save
        gen = Generation(
            version="v2.0.0",
            description="Major release",
            changes=[
                GenerationChange("FEAT-002", "fix", "Fix critical bug")
            ]
        )
        gen.save_to_db(test_db)

        # Load from DB
        loaded = Generation.from_db(test_db, gen.generation_id)

        assert loaded is not None
        assert loaded.version == "v2.0.0"
        assert loaded.description == "Major release"
        assert len(loaded.changes) == 1
        assert loaded.changes[0].change_id == "FEAT-002"

    def test_promote_generation(self, test_db):
        """Test promoting a generation"""
        gen = Generation(
            version="v3.0.0",
            changes=[GenerationChange("FEAT-003", "add", "New feature")]
        )
        gen.save_to_db(test_db)

        # Create a passing evolution
        evo = Evolution(
            generation_id=gen.generation_id,
            change_id="FEAT-003",
            tag="v3.0.0-rc.1",
            status="pass"
        )
        evo.save_to_db(test_db)

        # Promote
        result = gen.promote(test_db, gates=[], auto_tag=False)

        assert result["success"] is True
        assert gen.status == "promoted"
        assert gen.promoted_at is not None

    def test_promote_with_unproven_changes(self, test_db):
        """Test promoting fails with unproven changes"""
        from gryt.gates import AllChangesProvenGate

        gen = Generation(
            version="v4.0.0",
            changes=[GenerationChange("FEAT-004", "add", "Unproven feature")]
        )
        gen.save_to_db(test_db)

        # Try to promote without evolutions
        result = gen.promote(test_db, gates=[AllChangesProvenGate()], auto_tag=False)

        assert result["success"] is False
        assert gen.status == "draft"


class TestEvolution:
    """Test Evolution functionality"""

    def test_create_evolution(self, test_db):
        """Test creating an evolution"""
        # Create generation first
        gen = Generation(
            version="v5.0.0",
            changes=[GenerationChange("FEAT-005", "add", "Test feature")]
        )
        gen.save_to_db(test_db)

        # Create evolution
        evo = Evolution(
            generation_id=gen.generation_id,
            change_id="FEAT-005",
            tag="v5.0.0-rc.1"
        )
        evo.save_to_db(test_db)

        # Verify in database
        rows = test_db.query(
            "SELECT * FROM evolutions WHERE tag = ?",
            ("v5.0.0-rc.1",)
        )

        assert len(rows) == 1
        assert rows[0]["tag"] == "v5.0.0-rc.1"
        assert rows[0]["status"] == "pending"

    def test_generate_next_rc_tag(self, test_db):
        """Test RC tag auto-increment"""
        gen = Generation(
            version="v6.0.0",
            changes=[GenerationChange("FEAT-006", "add", "Feature")]
        )
        gen.save_to_db(test_db)

        # First evolution
        tag1 = Evolution.generate_next_rc_tag(test_db, "v6.0.0")
        assert tag1 == "v6.0.0-rc.1"

        # Save first evolution
        evo1 = Evolution(gen.generation_id, "FEAT-006", tag1)
        evo1.save_to_db(test_db)

        # Second evolution
        tag2 = Evolution.generate_next_rc_tag(test_db, "v6.0.0")
        assert tag2 == "v6.0.0-rc.2"

        # Save second evolution
        evo2 = Evolution(gen.generation_id, "FEAT-006", tag2)
        evo2.save_to_db(test_db)

        # Third evolution
        tag3 = Evolution.generate_next_rc_tag(test_db, "v6.0.0")
        assert tag3 == "v6.0.0-rc.3"

    def test_list_for_generation(self, test_db):
        """Test listing evolutions for a generation"""
        gen = Generation(
            version="v7.0.0",
            changes=[GenerationChange("FEAT-007", "add", "Feature")]
        )
        gen.save_to_db(test_db)

        # Create multiple evolutions
        for i in range(3):
            evo = Evolution(
                gen.generation_id,
                "FEAT-007",
                f"v7.0.0-rc.{i+1}"
            )
            evo.save_to_db(test_db)

        # List evolutions
        evolutions = Evolution.list_for_generation(test_db, gen.generation_id)

        assert len(evolutions) == 3
        # Evolutions are returned in DESC order (most recent first)
        tags = [e.tag for e in evolutions]
        assert "v7.0.0-rc.1" in tags
        assert "v7.0.0-rc.2" in tags
        assert "v7.0.0-rc.3" in tags

    def test_update_evolution_status(self, test_db):
        """Test updating evolution status"""
        gen = Generation(
            version="v8.0.0",
            changes=[GenerationChange("FEAT-008", "add", "Feature")]
        )
        gen.save_to_db(test_db)

        evo = Evolution(gen.generation_id, "FEAT-008", "v8.0.0-rc.1")
        evo.save_to_db(test_db)

        # Update status
        evo.status = "pass"
        evo.completed_at = datetime.now()
        evo.save_to_db(test_db)

        # Verify
        loaded = Evolution.from_db(test_db, evo.evolution_id)
        assert loaded.status == "pass"
        assert loaded.completed_at is not None
