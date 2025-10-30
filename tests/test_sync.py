"""Tests for CloudSync and bidirectional sync functionality (v1.0.0)"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from gryt.sync import CloudSync, CloudSyncHandler
from gryt.generation import Generation, GenerationChange
from gryt.evolution import Evolution


class TestCloudSyncPull:
    """Test CloudSync.pull() functionality"""

    def test_pull_new_generation(self, test_db):
        """Test pulling a new generation from cloud"""
        # Mock cloud client
        mock_client = Mock()
        mock_client.list_generations.return_value = {
            "generations": [
                {
                    "id": "cloud-gen-1",
                    "generation_id": "local-gen-1",
                    "version": "v1.0.0",
                    "description": "Cloud generation",
                    "status": "promoted",
                    "created_at": "2025-01-01T00:00:00Z",
                    "changes": [],
                }
            ]
        }

        sync = CloudSync(client=mock_client, data=test_db)
        result = sync.pull()

        assert result["new"] == 1
        assert result["updated"] == 0
        assert len(result["conflicts"]) == 0

        # Verify in database
        rows = test_db.query("SELECT * FROM generations WHERE version = ?", ("v1.0.0",))
        assert len(rows) == 1
        assert rows[0]["remote_id"] == "cloud-gen-1"
        assert rows[0]["sync_status"] == "synced"

    def test_pull_updated_generation(self, test_db):
        """Test pulling updates to existing generation"""
        # Create local generation with remote_id
        gen = Generation(
            version="v2.0.0",
            description="Original description",
            changes=[GenerationChange("CHG-001", "add", "Feature")]
        )
        gen.save_to_db(test_db)

        # Set remote_id manually
        test_db.update(
            "generations",
            {"remote_id": "cloud-gen-2", "sync_status": "synced"},
            "generation_id = ?",
            (gen.generation_id,)
        )

        # Mock cloud with updated version
        mock_client = Mock()
        mock_client.list_generations.return_value = {
            "generations": [
                {
                    "id": "cloud-gen-2",
                    "generation_id": gen.generation_id,
                    "version": "v2.0.0",
                    "description": "Updated description",
                    "status": "promoted",
                    "created_at": "2025-01-01T00:00:00Z",
                    "changes": [],
                }
            ]
        }

        sync = CloudSync(client=mock_client, data=test_db)
        result = sync.pull()

        assert result["new"] == 0
        assert result["updated"] == 1
        assert len(result["conflicts"]) == 0

        # Verify description was updated
        rows = test_db.query("SELECT * FROM generations WHERE version = ?", ("v2.0.0",))
        assert rows[0]["description"] == "Updated description"

    def test_pull_version_conflict(self, test_db):
        """Test pull detects version conflict (same version, no remote_id)"""
        # Create local generation without remote_id
        gen = Generation(
            version="v3.0.0",
            description="Local generation",
            changes=[GenerationChange("CHG-002", "add", "Feature")]
        )
        gen.save_to_db(test_db)

        # Mock cloud with same version, different id
        mock_client = Mock()
        mock_client.list_generations.return_value = {
            "generations": [
                {
                    "id": "cloud-gen-3",
                    "generation_id": "different-gen-id",
                    "version": "v3.0.0",
                    "description": "Cloud generation",
                    "status": "promoted",
                    "created_at": "2025-01-01T00:00:00Z",
                    "changes": [],
                }
            ]
        }

        sync = CloudSync(client=mock_client, data=test_db)
        result = sync.pull()

        assert result["new"] == 0
        assert result["updated"] == 0
        assert len(result["conflicts"]) == 1
        assert result["conflicts"][0]["version"] == "v3.0.0"
        assert "same version" in result["conflicts"][0]["reason"].lower()

    def test_pull_empty_cloud(self, test_db):
        """Test pull with no cloud generations"""
        mock_client = Mock()
        mock_client.list_generations.return_value = {"generations": []}

        sync = CloudSync(client=mock_client, data=test_db)
        result = sync.pull()

        assert result["new"] == 0
        assert result["updated"] == 0
        assert len(result["conflicts"]) == 0


class TestCloudSyncPush:
    """Test CloudSync.push() functionality"""

    def test_push_new_generation(self, test_db):
        """Test pushing new generation to cloud"""
        # Create local generation without remote_id
        gen = Generation(
            version="v4.0.0",
            description="Local generation",
            changes=[GenerationChange("CHG-003", "add", "Feature")]
        )
        gen.save_to_db(test_db)

        # Mock cloud client
        mock_client = Mock()
        mock_client.get_generation_by_version.side_effect = RuntimeError("Not found")
        mock_client.create_generation.return_value = {"id": "cloud-gen-4"}

        sync = CloudSync(client=mock_client, data=test_db)
        result = sync.push()

        assert result["created"] == 1
        assert result["updated"] == 0
        assert len(result["errors"]) == 0

        # Verify remote_id was saved
        rows = test_db.query("SELECT * FROM generations WHERE version = ?", ("v4.0.0",))
        assert rows[0]["remote_id"] == "cloud-gen-4"
        assert rows[0]["sync_status"] == "synced"

    def test_push_update_existing(self, test_db):
        """Test pushing update to existing generation"""
        # Create local generation with remote_id
        gen = Generation(
            version="v5.0.0",
            description="Updated locally",
            changes=[GenerationChange("CHG-004", "fix", "Bug fix")]
        )
        gen.save_to_db(test_db)

        # Set remote_id manually
        test_db.update(
            "generations",
            {"remote_id": "cloud-gen-5"},
            "generation_id = ?",
            (gen.generation_id,)
        )

        # Mock cloud client
        mock_client = Mock()
        mock_client.update_generation.return_value = {"success": True}

        sync = CloudSync(client=mock_client, data=test_db)
        result = sync.push()

        assert result["created"] == 0
        assert result["updated"] == 1
        assert len(result["errors"]) == 0

        # Verify update was called
        mock_client.update_generation.assert_called_once()

    def test_push_version_conflict(self, test_db):
        """Test push detects version conflict in cloud"""
        # Create local generation without remote_id
        gen = Generation(
            version="v6.0.0",
            description="Local generation",
            changes=[GenerationChange("CHG-005", "add", "Feature")]
        )
        gen.save_to_db(test_db)

        # Mock cloud client to return existing version
        mock_client = Mock()
        mock_client.get_generation_by_version.return_value = {
            "id": "cloud-gen-6",
            "version": "v6.0.0"
        }

        sync = CloudSync(client=mock_client, data=test_db)
        result = sync.push()

        assert result["created"] == 0
        assert result["updated"] == 0
        assert len(result["errors"]) == 1
        assert result["errors"][0]["version"] == "v6.0.0"
        assert "already exists" in result["errors"][0]["error"].lower()

    def test_push_specific_version(self, test_db):
        """Test pushing specific version only"""
        # Create two local generations
        gen1 = Generation(
            version="v7.0.0",
            changes=[GenerationChange("CHG-006", "add", "Feature 1")]
        )
        gen1.save_to_db(test_db)

        gen2 = Generation(
            version="v7.1.0",
            changes=[GenerationChange("CHG-007", "add", "Feature 2")]
        )
        gen2.save_to_db(test_db)

        # Mock cloud client
        mock_client = Mock()
        mock_client.get_generation_by_version.side_effect = RuntimeError("Not found")
        mock_client.create_generation.return_value = {"id": "cloud-gen-7"}

        sync = CloudSync(client=mock_client, data=test_db)
        result = sync.push(version="v7.0.0")

        # Only v7.0.0 should be pushed
        assert result["created"] == 1
        mock_client.create_generation.assert_called_once()


class TestCloudSyncStatus:
    """Test CloudSync.status() functionality"""

    def test_status_summary(self, test_db):
        """Test status summary for all generations"""
        # Create generations with different sync states
        gen1 = Generation(version="v8.0.0", changes=[])
        gen1.save_to_db(test_db)
        test_db.update(
            "generations",
            {"remote_id": "cloud-1", "sync_status": "synced"},
            "generation_id = ?",
            (gen1.generation_id,)
        )

        gen2 = Generation(version="v8.1.0", changes=[])
        gen2.save_to_db(test_db)
        # Leave as not_synced

        gen3 = Generation(version="v8.2.0", changes=[])
        gen3.save_to_db(test_db)
        test_db.update(
            "generations",
            {"sync_status": "conflict"},
            "generation_id = ?",
            (gen3.generation_id,)
        )

        mock_client = Mock()
        sync = CloudSync(client=mock_client, data=test_db)
        result = sync.status()

        assert result["summary"]["total"] == 3
        assert result["summary"]["synced"] == 1
        assert result["summary"]["pending"] == 1
        assert result["summary"]["conflicts"] == 1

    def test_status_specific_version(self, test_db):
        """Test status for specific version"""
        # Create generation with evolution
        gen = Generation(
            version="v9.0.0",
            changes=[GenerationChange("CHG-008", "add", "Feature")]
        )
        gen.save_to_db(test_db)

        evo = Evolution(
            generation_id=gen.generation_id,
            change_id="CHG-008",
            tag="v9.0.0-rc.1",
            status="pass"
        )
        evo.save_to_db(test_db)

        test_db.update(
            "generations",
            {"remote_id": "cloud-9", "sync_status": "synced"},
            "generation_id = ?",
            (gen.generation_id,)
        )

        mock_client = Mock()
        sync = CloudSync(client=mock_client, data=test_db)
        result = sync.status(version="v9.0.0")

        assert result["generation"]["version"] == "v9.0.0"
        assert result["generation"]["sync_status"] == "synced"
        assert len(result["generation"]["evolutions"]) == 1


class TestCloudSyncHandler:
    """Test CloudSyncHandler event-driven sync"""

    def test_attach_to_event_bus(self, test_db):
        """Test handler attaches to event bus"""
        from gryt.events import EventBus

        mock_client = Mock()
        bus = EventBus()
        handler = CloudSyncHandler(client=mock_client, data=test_db, execution_mode="cloud")

        handler.attach(bus)

        # Verify handler subscribed to events
        assert "generation.created" in bus._handlers
        assert "generation.promoted" in bus._handlers

    @patch("gryt.sync.CloudSync.push")
    def test_sync_on_promote_hybrid_mode(self, mock_push, test_db):
        """Test sync happens on promote in hybrid mode"""
        from gryt.events import EventBus

        mock_client = Mock()
        bus = EventBus()
        handler = CloudSyncHandler(client=mock_client, data=test_db, execution_mode="hybrid")
        handler.attach(bus)

        # Create and promote generation
        gen = Generation(
            version="v10.0.0",
            changes=[GenerationChange("CHG-009", "add", "Feature")]
        )
        gen.save_to_db(test_db)

        # Emit promotion event
        bus.emit("generation.promoted", {"generation": gen})

        # Verify push was called
        assert mock_push.called

    @patch("gryt.sync.CloudSync.push")
    def test_no_sync_in_local_mode(self, mock_push, test_db):
        """Test no auto-sync in local mode"""
        from gryt.events import EventBus

        mock_client = Mock()
        bus = EventBus()
        handler = CloudSyncHandler(client=mock_client, data=test_db, execution_mode="local")
        handler.attach(bus)

        # Create generation
        gen = Generation(
            version="v11.0.0",
            changes=[GenerationChange("CHG-010", "add", "Feature")]
        )
        gen.save_to_db(test_db)

        # Emit creation event
        bus.emit("generation.created", {"generation": gen})

        # Verify push was NOT called
        assert not mock_push.called


class TestCloudSyncIntegration:
    """Integration tests for full sync workflows"""

    def test_full_bidirectional_sync(self, test_db):
        """Test complete pull-push workflow"""
        mock_client = Mock()

        # Initial cloud state: one generation
        mock_client.list_generations.return_value = {
            "generations": [
                {
                    "id": "cloud-gen-100",
                    "generation_id": "local-gen-100",
                    "version": "v100.0.0",
                    "description": "Cloud generation",
                    "status": "promoted",
                    "created_at": "2025-01-01T00:00:00Z",
                    "changes": [],
                }
            ]
        }

        sync = CloudSync(client=mock_client, data=test_db)

        # Pull from cloud
        pull_result = sync.pull()
        assert pull_result["new"] == 1

        # Create new local generation
        gen = Generation(
            version="v101.0.0",
            description="New local generation",
            changes=[GenerationChange("CHG-100", "add", "Feature")]
        )
        gen.save_to_db(test_db)

        # Configure mock for push
        mock_client.get_generation_by_version.side_effect = RuntimeError("Not found")
        mock_client.create_generation.return_value = {"id": "cloud-gen-101"}

        # Push to cloud
        push_result = sync.push()
        assert push_result["created"] == 1

        # Verify both generations are in local DB
        all_gens = test_db.query("SELECT * FROM generations")
        assert len(all_gens) == 2

    def test_conflict_resolution_workflow(self, test_db):
        """Test workflow for resolving version conflicts"""
        # Create local generation
        gen = Generation(
            version="v200.0.0",
            description="Local version",
            changes=[GenerationChange("CHG-200", "add", "Feature")]
        )
        gen.save_to_db(test_db)

        mock_client = Mock()
        # Cloud has same version
        mock_client.get_generation_by_version.return_value = {
            "id": "cloud-gen-200",
            "version": "v200.0.0"
        }

        sync = CloudSync(client=mock_client, data=test_db)

        # Try to push - should fail with conflict
        push_result = sync.push()
        assert len(push_result["errors"]) == 1
        assert "already exists" in push_result["errors"][0]["error"].lower()

        # Resolution: rename local version
        test_db.update(
            "generations",
            {"version": "v200.1.0"},
            "generation_id = ?",
            (gen.generation_id,)
        )

        # Configure mock for new version
        mock_client.get_generation_by_version.side_effect = RuntimeError("Not found")
        mock_client.create_generation.return_value = {"id": "cloud-gen-201"}

        # Retry push - should succeed
        push_result = sync.push(version="v200.1.0")
        assert push_result["created"] == 1
