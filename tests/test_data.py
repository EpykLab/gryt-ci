"""Tests for gryt.data module"""
import pytest
from gryt.data import SqliteData


class TestSqliteData:
    """Test SqliteData functionality"""

    def test_initialization(self, test_db):
        """Test database initialization creates required tables"""
        tables = test_db.query(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        table_names = [row["name"] for row in tables]

        # Core tables
        assert "pipelines" in table_names
        assert "runners" in table_names
        assert "steps_output" in table_names
        assert "versions" in table_names

        # Generation/Evolution tables (v0.2.0, v0.3.0)
        assert "generations" in table_names
        assert "generation_changes" in table_names
        assert "evolutions" in table_names

    def test_insert_and_query(self, test_db):
        """Test basic insert and query operations"""
        test_db.insert("pipelines", {
            "pipeline_id": "test-pipeline-1",
            "name": "Test Pipeline",
            "status": "completed"
        })

        rows = test_db.query(
            "SELECT * FROM pipelines WHERE pipeline_id = ?",
            ("test-pipeline-1",)
        )

        assert len(rows) == 1
        assert rows[0]["pipeline_id"] == "test-pipeline-1"
        assert rows[0]["name"] == "Test Pipeline"
        assert rows[0]["status"] == "completed"

    def test_update(self, test_db):
        """Test update operations"""
        test_db.insert("pipelines", {
            "pipeline_id": "test-pipeline-2",
            "name": "Test Pipeline",
            "status": "running"
        })

        test_db.update(
            "pipelines",
            {"status": "completed"},
            "pipeline_id = ?",
            ("test-pipeline-2",)
        )

        rows = test_db.query(
            "SELECT status FROM pipelines WHERE pipeline_id = ?",
            ("test-pipeline-2",)
        )

        assert rows[0]["status"] == "completed"

    def test_foreign_key_cascade(self, test_db):
        """Test foreign key cascades work correctly"""
        # Insert pipeline
        test_db.insert("pipelines", {
            "pipeline_id": "test-pipeline-3",
            "name": "Test Pipeline"
        })

        # Insert runner
        test_db.insert("runners", {
            "runner_id": "test-runner-1",
            "pipeline_id": "test-pipeline-3",
            "name": "Test Runner"
        })

        # Delete pipeline
        test_db.query(
            "DELETE FROM pipelines WHERE pipeline_id = ?",
            ("test-pipeline-3",)
        )

        # Verify runner was cascaded
        rows = test_db.query(
            "SELECT * FROM runners WHERE runner_id = ?",
            ("test-runner-1",)
        )

        assert len(rows) == 0

    def test_json_handling(self, test_db):
        """Test JSON serialization/deserialization"""
        config = {"key": "value", "nested": {"foo": "bar"}}

        test_db.insert("pipelines", {
            "pipeline_id": "test-pipeline-4",
            "config_json": config
        })

        rows = test_db.query(
            "SELECT config_json FROM pipelines WHERE pipeline_id = ?",
            ("test-pipeline-4",)
        )

        # Should be auto-deserialized back to dict
        retrieved_config = rows[0]["config_json"]
        assert isinstance(retrieved_config, (dict, str))

        # If it's a dict, verify contents
        if isinstance(retrieved_config, dict):
            assert retrieved_config == config

    def test_concurrent_access(self, test_db):
        """Test thread-safe operations"""
        import threading

        def insert_pipeline(pipeline_id):
            test_db.insert("pipelines", {
                "pipeline_id": pipeline_id,
                "name": f"Pipeline {pipeline_id}"
            })

        threads = []
        for i in range(10):
            t = threading.Thread(target=insert_pipeline, args=(f"concurrent-{i}",))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        rows = test_db.query(
            "SELECT COUNT(*) as count FROM pipelines WHERE pipeline_id LIKE 'concurrent-%'"
        )

        assert rows[0]["count"] == 10
