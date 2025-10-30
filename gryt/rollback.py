"""
Rollback System (v1.0.0)

Provides database snapshot and rollback capabilities for safe evolution.
"""
from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from .data import SqliteData


class RollbackManager:
    """Manages database snapshots and rollback operations"""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.snapshot_dir = self.db_path.parent / "snapshots"
        self.snapshot_dir.mkdir(exist_ok=True)

    def create_snapshot(self, label: Optional[str] = None) -> str:
        """Create a database snapshot

        Args:
            label: Optional label for the snapshot

        Returns:
            Snapshot ID
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_id = f"snapshot_{timestamp}"
        if label:
            snapshot_id += f"_{label}"

        snapshot_path = self.snapshot_dir / f"{snapshot_id}.db"

        # Copy database file
        shutil.copy2(self.db_path, snapshot_path)

        # Store metadata
        self._store_snapshot_metadata(snapshot_id, label)

        return snapshot_id

    def _store_snapshot_metadata(self, snapshot_id: str, label: Optional[str]) -> None:
        """Store snapshot metadata in database"""
        data = SqliteData(db_path=str(self.db_path))
        try:
            # Ensure snapshots table exists
            data.query("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    label TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    db_size_bytes INTEGER
                )
            """)

            # Get database size
            db_size = self.db_path.stat().st_size

            data.insert("snapshots", {
                "snapshot_id": snapshot_id,
                "label": label,
                "created_at": datetime.now().isoformat(),
                "db_size_bytes": db_size
            })
        finally:
            data.close()

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """List all available snapshots"""
        data = SqliteData(db_path=str(self.db_path))
        try:
            # Ensure table exists
            data.query("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    label TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    db_size_bytes INTEGER
                )
            """)

            rows = data.query("""
                SELECT * FROM snapshots
                ORDER BY created_at DESC
            """)
            return [dict(row) for row in rows]
        finally:
            data.close()

    def rollback_to_snapshot(self, snapshot_id: str, backup_current: bool = True) -> None:
        """Rollback database to a previous snapshot

        Args:
            snapshot_id: ID of snapshot to rollback to
            backup_current: If True, create backup of current state before rollback
        """
        snapshot_path = self.snapshot_dir / f"{snapshot_id}.db"

        if not snapshot_path.exists():
            raise ValueError(f"Snapshot not found: {snapshot_id}")

        # Backup current state if requested
        if backup_current:
            self.create_snapshot(label="pre_rollback")

        # Perform rollback by replacing database file
        shutil.copy2(snapshot_path, self.db_path)

    def delete_snapshot(self, snapshot_id: str) -> None:
        """Delete a snapshot

        Args:
            snapshot_id: ID of snapshot to delete
        """
        snapshot_path = self.snapshot_dir / f"{snapshot_id}.db"

        if snapshot_path.exists():
            snapshot_path.unlink()

        # Remove from metadata
        data = SqliteData(db_path=str(self.db_path))
        try:
            data.query(
                "DELETE FROM snapshots WHERE snapshot_id = ?",
                (snapshot_id,)
            )
        finally:
            data.close()

    def get_snapshot_diff(self, snapshot_id: str) -> Dict[str, Any]:
        """Get differences between current state and a snapshot

        Args:
            snapshot_id: ID of snapshot to compare with

        Returns:
            Dictionary with differences
        """
        snapshot_path = self.snapshot_dir / f"{snapshot_id}.db"

        if not snapshot_path.exists():
            raise ValueError(f"Snapshot not found: {snapshot_id}")

        # Connect to both databases
        current_conn = sqlite3.connect(self.db_path)
        snapshot_conn = sqlite3.connect(snapshot_path)

        diff = {
            "generations": self._diff_table(current_conn, snapshot_conn, "generations"),
            "evolutions": self._diff_table(current_conn, snapshot_conn, "evolutions"),
            "pipelines": self._diff_table(current_conn, snapshot_conn, "pipelines"),
        }

        current_conn.close()
        snapshot_conn.close()

        return diff

    def _diff_table(
        self,
        current_conn: sqlite3.Connection,
        snapshot_conn: sqlite3.Connection,
        table_name: str
    ) -> Dict[str, int]:
        """Calculate differences in a table"""
        try:
            current_count = current_conn.execute(
                f"SELECT COUNT(*) FROM {table_name}"
            ).fetchone()[0]

            snapshot_count = snapshot_conn.execute(
                f"SELECT COUNT(*) FROM {table_name}"
            ).fetchone()[0]

            return {
                "current_count": current_count,
                "snapshot_count": snapshot_count,
                "delta": current_count - snapshot_count
            }
        except sqlite3.OperationalError:
            # Table doesn't exist in one of the databases
            return {
                "current_count": 0,
                "snapshot_count": 0,
                "delta": 0
            }

    def cleanup_old_snapshots(self, keep_count: int = 10) -> List[str]:
        """Delete old snapshots, keeping only the most recent

        Args:
            keep_count: Number of snapshots to keep

        Returns:
            List of deleted snapshot IDs
        """
        snapshots = self.list_snapshots()

        if len(snapshots) <= keep_count:
            return []

        # Delete oldest snapshots
        to_delete = snapshots[keep_count:]
        deleted = []

        for snapshot in to_delete:
            try:
                self.delete_snapshot(snapshot["snapshot_id"])
                deleted.append(snapshot["snapshot_id"])
            except Exception:
                pass

        return deleted
