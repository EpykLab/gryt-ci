"""
Tests for Audit Trail, Rollback, and Hot-fix features (v1.0.0)
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

import pytest

from gryt import (
    AuditTrail,
    RollbackManager,
    HotfixWorkflow,
    HotfixGate,
    create_hotfix,
    Generation,
    GenerationChange,
    Evolution,
    ComplianceReport,
    generate_compliance_report,
)


class TestAuditTrail:
    """Test audit trail logging and export"""

    def test_log_event(self, test_db):
        """Test logging an audit event"""
        audit = AuditTrail(test_db)

        event_id = audit.log_event(
            event_type="generation",
            resource_type="generation",
            resource_id="gen-123",
            action="created",
            status="success",
            actor="test-user",
            details={"version": "v1.0.0"},
        )

        assert event_id.startswith("audit-")

        # Verify event was logged
        events = test_db.query(
            "SELECT * FROM audit_events WHERE event_id = ?", (event_id,)
        )
        assert len(events) == 1
        assert events[0]["event_type"] == "generation"
        assert events[0]["action"] == "created"
        assert events[0]["actor"] == "test-user"

    def test_export_json(self, test_db, temp_dir):
        """Test JSON export"""
        audit = AuditTrail(test_db)

        # Log some events
        audit.log_event("generation", "generation", "gen-1", "created")
        audit.log_event("evolution", "evolution", "evo-1", "started")

        output_path = temp_dir / "audit.json"
        audit.export_full_audit_trail(output_path, format="json")

        assert output_path.exists()

        # Verify JSON content
        with open(output_path, "r") as f:
            data = json.load(f)

        assert "exported_at" in data
        assert "audit_events" in data
        assert len(data["audit_events"]) >= 2

    def test_export_csv(self, test_db, temp_dir):
        """Test CSV export"""
        audit = AuditTrail(test_db)

        # Log event
        audit.log_event("generation", "generation", "gen-1", "created")

        output_path = temp_dir / "audit.csv"
        audit.export_full_audit_trail(output_path, format="csv")

        assert output_path.exists()

        # Verify CSV has header and data
        content = output_path.read_text()
        lines = content.strip().split("\n")
        assert len(lines) >= 2  # Header + at least 1 event
        assert "event_id" in lines[0]

    def test_export_html(self, test_db, temp_dir):
        """Test HTML export"""
        audit = AuditTrail(test_db)

        # Log event
        audit.log_event("generation", "generation", "gen-1", "created")

        output_path = temp_dir / "audit.html"
        audit.export_full_audit_trail(output_path, format="html")

        assert output_path.exists()

        # Verify HTML content
        content = output_path.read_text()
        assert "<!DOCTYPE html>" in content
        assert "Audit Trail Report" in content


class TestRollbackManager:
    """Test database snapshot and rollback"""

    def test_create_snapshot(self, test_db_path):
        """Test creating a snapshot"""
        manager = RollbackManager(test_db_path)

        snapshot_id = manager.create_snapshot(label="test-snapshot")

        assert snapshot_id.startswith("snapshot_")

        # Verify snapshot file exists
        snapshot_path = manager.snapshot_dir / f"{snapshot_id}.db"
        assert snapshot_path.exists()

    def test_list_snapshots(self, test_db_path):
        """Test listing snapshots"""
        manager = RollbackManager(test_db_path)

        # Create snapshots
        id1 = manager.create_snapshot(label="first")
        id2 = manager.create_snapshot(label="second")

        snapshots = manager.list_snapshots()

        assert len(snapshots) >= 2
        snapshot_ids = [s["snapshot_id"] for s in snapshots]
        assert id1 in snapshot_ids
        assert id2 in snapshot_ids

    def test_rollback_to_snapshot(self, test_db, test_db_path):
        """Test rollback to previous state"""
        manager = RollbackManager(test_db_path)

        # Create initial state
        test_db.insert("generations", {"generation_id": "gen-1", "version": "v1.0.0"})
        snapshot_id = manager.create_snapshot(label="before-change")

        # Make changes
        test_db.insert("generations", {"generation_id": "gen-2", "version": "v2.0.0"})

        # Verify both generations exist
        gens = test_db.query("SELECT * FROM generations")
        assert len(gens) == 2

        # Rollback
        manager.rollback_to_snapshot(snapshot_id, backup_current=False)

        # Reconnect to database to see changes
        test_db.close()
        from gryt.data import SqliteData
        test_db_new = SqliteData(db_path=str(test_db_path))

        # Verify only gen-1 exists
        gens = test_db_new.query("SELECT * FROM generations")
        assert len(gens) == 1
        assert gens[0]["generation_id"] == "gen-1"
        test_db_new.close()


class TestHotfixWorkflow:
    """Test hot-fix generation workflow"""

    def test_hotfix_gate_passes_with_one_evolution(self, test_db):
        """Test HotfixGate passes with one passing evolution"""
        # Create generation with change
        change = GenerationChange(
            change_id="HOTFIX-001", change_type="fix", title="Critical bug fix"
        )
        gen = Generation(version="v1.0.1", description="Hot-fix", changes=[change])
        gen.save_to_db(test_db)

        # Create passing evolution
        evo = Evolution(
            tag="v1.0.1-rc.1",
            generation_id=gen.generation_id,
            change_id="HOTFIX-001",
            status="pass",
        )
        evo.save_to_db(test_db)

        # Check gate
        gate = HotfixGate()
        result = gate.check(gen, test_db)

        assert result.passed is True

    def test_hotfix_gate_fails_with_pending_evolution(self, test_db):
        """Test HotfixGate fails if evolution is pending"""
        # Create generation with change
        change = GenerationChange(
            change_id="HOTFIX-002", change_type="fix", title="Another fix"
        )
        gen = Generation(version="v1.0.2", description="Hot-fix", changes=[change])
        gen.save_to_db(test_db)

        # Create both passing and pending evolutions to test pending detection
        evo_pass = Evolution(
            tag="v1.0.2-rc.1",
            generation_id=gen.generation_id,
            change_id="HOTFIX-002",
            status="pass",
        )
        evo_pass.save_to_db(test_db)

        evo_pending = Evolution(
            tag="v1.0.2-rc.2",
            generation_id=gen.generation_id,
            change_id="HOTFIX-002",
            status="pending",
        )
        evo_pending.save_to_db(test_db)

        # Check gate
        gate = HotfixGate()
        result = gate.check(gen, test_db)

        assert result.passed is False
        assert "pending" in result.message.lower()

    def test_calculate_hotfix_version(self, test_db):
        """Test hot-fix version calculation"""
        workflow = HotfixWorkflow(test_db)

        # Create base generation
        gen = Generation(version="v1.2.0", description="Base release", changes=[])
        gen.save_to_db(test_db)

        # Calculate hot-fix version
        hotfix_version = workflow._calculate_hotfix_version("v1.2.0")

        assert hotfix_version == "v1.2.1"

    def test_calculate_hotfix_version_increments(self, test_db):
        """Test hot-fix version increments properly"""
        workflow = HotfixWorkflow(test_db)

        # Create base and first hot-fix
        gen1 = Generation(version="v1.2.0", description="Base", changes=[])
        gen1.save_to_db(test_db)

        gen2 = Generation(version="v1.2.1", description="First hot-fix", changes=[])
        gen2.save_to_db(test_db)

        # Calculate next hot-fix version
        hotfix_version = workflow._calculate_hotfix_version("v1.2.0")

        assert hotfix_version == "v1.2.2"

    def test_create_hotfix_helper(self, test_db_path):
        """Test create_hotfix helper function"""
        generation = create_hotfix(
            test_db_path, base_version="v2.0.0", issue_id="BUG-123", title="Fix crash on startup"
        )

        assert generation.version == "v2.0.1"
        assert len(generation.changes) == 1
        assert generation.changes[0].change_id == "BUG-123"
        assert generation.changes[0].type == "fix"

        # Verify saved to database
        from gryt.data import SqliteData
        test_db = SqliteData(db_path=str(test_db_path))
        rows = test_db.query("SELECT * FROM generations WHERE version = ?", ("v2.0.1",))
        assert len(rows) == 1
        test_db.close()


class TestComplianceReport:
    """Test NIST 800-161 compliance report generation"""

    def test_generate_report(self, test_db, temp_dir):
        """Test generating compliance report"""
        # Create some test data
        change = GenerationChange(
            change_id="TEST-001", change_type="add", title="New feature"
        )
        gen = Generation(version="v1.0.0", description="Test release", changes=[change])
        gen.save_to_db(test_db)

        evo = Evolution(
            tag="v1.0.0-rc.1",
            generation_id=gen.generation_id,
            change_id="TEST-001",
            status="pass",
        )
        evo.save_to_db(test_db)

        # Generate report
        report = ComplianceReport(test_db)
        output_path = temp_dir / "compliance.html"
        report.generate_report(output_path)

        assert output_path.exists()

        # Verify HTML content
        content = output_path.read_text()
        assert "<!DOCTYPE html>" in content
        assert "NIST 800-161 Compliance Report" in content
        assert "gryt-ci" in content
        assert "Change Management" in content
        assert "Testing & Validation" in content
        assert "Audit & Accountability" in content

    def test_compliance_report_includes_statistics(self, test_db, temp_dir):
        """Test report includes relevant statistics"""
        # Create multiple generations and evolutions
        for i in range(3):
            change = GenerationChange(
                change_id=f"FEAT-{i:03d}", change_type="add", title=f"Feature {i}"
            )
            gen = Generation(version=f"v1.{i}.0", description=f"Release {i}", changes=[change])
            gen.save_to_db(test_db)

            evo = Evolution(
                tag=f"v1.{i}.0-rc.1",
                generation_id=gen.generation_id,
                change_id=f"FEAT-{i:03d}",
                status="pass",
            )
            evo.save_to_db(test_db)

        # Generate report
        report = ComplianceReport(test_db)
        output_path = temp_dir / "compliance.html"
        report.generate_report(output_path)

        content = output_path.read_text()

        # Should show 3 generations
        assert "3" in content
        # Should show pass rate
        assert "100" in content or "pass" in content.lower()

    def test_generate_compliance_report_helper(self, test_db_path, temp_dir):
        """Test generate_compliance_report helper function"""
        output_path = temp_dir / "compliance-helper.html"

        generate_compliance_report(test_db_path, output_path)

        assert output_path.exists()
        content = output_path.read_text()
        assert "NIST 800-161" in content


class TestIntegration:
    """Integration tests for v1.0.0 workflow"""

    def test_complete_hotfix_workflow(self, test_db, test_db_path):
        """Test complete hot-fix workflow from creation to promotion"""
        # Create base generation
        base_gen = Generation(version="v3.0.0", description="Production release", changes=[])
        base_gen.save_to_db(test_db)

        # Step 1: Create hot-fix
        hotfix = create_hotfix(test_db_path, "v3.0.0", "CRIT-999", "Fix security vulnerability")

        assert hotfix.version == "v3.0.1"
        assert hotfix.status == "draft"

        # Step 2: Create evolution (simulate pipeline run)
        evo = Evolution(
            tag="v3.0.1-rc.1",
            generation_id=hotfix.generation_id,
            change_id="CRIT-999",
            status="pass",
        )
        evo.save_to_db(test_db)

        # Step 3: Promote hot-fix
        workflow = HotfixWorkflow(test_db)
        result = workflow.promote_hotfix(hotfix, auto_tag=False)

        assert result["success"] is True
        assert "message" in result

        # Verify generation is promoted
        updated = Generation.from_db(test_db, hotfix.generation_id)
        assert updated.status == "promoted"
        assert updated.promoted_at is not None
        assert updated.version == "v3.0.1"

    def test_audit_trail_captures_workflow(self, test_db, test_db_path, temp_dir):
        """Test audit trail captures complete workflow"""
        audit = AuditTrail(test_db)

        # Log workflow events
        audit.log_event("generation", "generation", "gen-1", "created")

        hotfix = create_hotfix(test_db_path, "v4.0.0", "BUG-111", "Fix")
        audit.log_event(
            "generation", "generation", hotfix.generation_id, "hotfix_created"
        )

        evo = Evolution(
            tag="v4.0.1-rc.1",
            generation_id=hotfix.generation_id,
            change_id="BUG-111",
            status="pass",
        )
        evo.save_to_db(test_db)
        audit.log_event("evolution", "evolution", evo.evolution_id, "completed")

        # Export audit trail
        output_path = temp_dir / "workflow-audit.json"
        audit.export_full_audit_trail(output_path, format="json")

        # Verify events captured
        with open(output_path, "r") as f:
            data = json.load(f)

        events = data["audit_events"]
        assert len(events) >= 3
        event_actions = [e["action"] for e in events]
        assert "created" in event_actions
        assert "hotfix_created" in event_actions
        assert "completed" in event_actions
