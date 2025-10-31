"""
Evolution system (v0.3.0)

An Evolution is a point-in-time proof that realizes one or more generation changes.
Each evolution is tagged with a release candidate version (vX.Y.Z-rc.N).
"""
from __future__ import annotations

import re
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .data import SqliteData
from .events import get_event_bus
from .generation import Generation


class Evolution:
    """
    An Evolution proves one or more changes from a Generation.

    Attributes:
        evolution_id: Unique identifier
        generation_id: Parent generation ID
        change_id: Change being proven
        tag: RC tag (e.g., "v2.2.0-rc.1")
        status: pending|running|pass|fail
        pipeline_run_id: Link to pipeline execution
        started_at: When evolution started
        completed_at: When evolution completed
        sync_status: not_synced|syncing|synced|conflict
        remote_id: ID in cloud (if synced)
    """

    def __init__(
        self,
        generation_id: str,
        change_id: str,
        tag: str,
        evolution_id: Optional[str] = None,
        status: str = "pending",
        pipeline_run_id: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        sync_status: str = "not_synced",
        remote_id: Optional[str] = None,
        created_by: Optional[str] = None,
    ):
        self.evolution_id = evolution_id or str(uuid.uuid4())
        self.generation_id = generation_id
        self.change_id = change_id
        self.tag = tag
        self.status = status
        self.pipeline_run_id = pipeline_run_id
        self.started_at = started_at or datetime.now()
        self.completed_at = completed_at
        self.sync_status = sync_status
        self.remote_id = remote_id
        self.created_by = created_by

    @classmethod
    def from_db(cls, data: SqliteData, evolution_id: str) -> Optional[Evolution]:
        """Load an Evolution from the database"""
        rows = data.query(
            "SELECT * FROM evolutions WHERE evolution_id = ?", (evolution_id,)
        )
        if not rows:
            return None

        row = rows[0]

        # Parse datetime strings from DB
        started_at = row.get("started_at")
        if started_at and isinstance(started_at, str):
            try:
                started_at = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                started_at = None

        completed_at = row.get("completed_at")
        if completed_at and isinstance(completed_at, str):
            try:
                completed_at = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                completed_at = None

        return cls(
            evolution_id=row["evolution_id"],
            generation_id=row["generation_id"],
            change_id=row["change_id"],
            tag=row["tag"],
            status=row["status"],
            pipeline_run_id=row.get("pipeline_run_id"),
            started_at=started_at,
            completed_at=completed_at,
            sync_status=row.get("sync_status", "not_synced"),
            remote_id=row.get("remote_id"),
            created_by=row.get("created_by"),
        )

    def save_to_db(self, data: SqliteData, emit_event: bool = True) -> None:
        """Save this Evolution to the database"""
        # Check if exists
        existing = data.query(
            "SELECT evolution_id FROM evolutions WHERE evolution_id = ?",
            (self.evolution_id,),
        )

        is_new = not existing

        evo_dict = {
            "evolution_id": self.evolution_id,
            "generation_id": self.generation_id,
            "change_id": self.change_id,
            "tag": self.tag,
            "status": self.status,
            "pipeline_run_id": self.pipeline_run_id,
            "completed_at": self.completed_at,
            "sync_status": self.sync_status,
            "remote_id": self.remote_id,
            "created_by": self.created_by,
        }

        if existing:
            # Update
            data.update(
                "evolutions",
                evo_dict,
                "evolution_id = ?",
                (self.evolution_id,),
            )
        else:
            # Insert
            evo_dict["started_at"] = self.started_at
            data.insert("evolutions", evo_dict)

        # Emit event
        if emit_event:
            bus = get_event_bus()
            event_name = "evolution.created" if is_new else "evolution.updated"
            if self.status == "pass":
                event_name = "evolution.completed"
            elif self.status == "fail":
                event_name = "evolution.failed"
            bus.emit(event_name, {"evolution": self.to_dict()})

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "evolution_id": self.evolution_id,
            "generation_id": self.generation_id,
            "change_id": self.change_id,
            "tag": self.tag,
            "status": self.status,
            "pipeline_run_id": self.pipeline_run_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "sync_status": self.sync_status,
            "remote_id": self.remote_id,
            "created_by": self.created_by,
        }

    def create_git_tag(self, repo_path: Optional[Path] = None) -> bool:
        """
        Create a git tag for this evolution.

        Returns True if successful, False otherwise.
        """
        repo = repo_path or Path.cwd()
        try:
            # Create annotated tag
            message = f"Evolution {self.evolution_id}\nChange: {self.change_id}\nStatus: {self.status}"
            subprocess.run(
                ["git", "tag", "-a", self.tag, "-m", message],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def list_for_generation(data: SqliteData, generation_id: str) -> List[Evolution]:
        """List all evolutions for a generation"""
        rows = data.query(
            "SELECT evolution_id FROM evolutions WHERE generation_id = ? ORDER BY started_at DESC",
            (generation_id,),
        )
        return [
            Evolution.from_db(data, row["evolution_id"])
            for row in rows
            if Evolution.from_db(data, row["evolution_id"])
        ]

    @staticmethod
    def generate_next_rc_tag(data: SqliteData, version: str) -> str:
        """
        Generate the next RC tag for a version.

        Examples:
            - If no RCs exist for v2.2.0, return "v2.2.0-rc.1"
            - If v2.2.0-rc.1 exists, return "v2.2.0-rc.2"
        """
        # Ensure version starts with 'v'
        if not version.startswith("v"):
            version = f"v{version}"

        # Query existing RC tags for this version
        pattern = f"{version}-rc.%"
        rows = data.query(
            "SELECT tag FROM evolutions WHERE tag LIKE ? ORDER BY tag DESC",
            (pattern,),
        )

        if not rows:
            return f"{version}-rc.1"

        # Parse highest RC number
        highest_rc = 0
        rc_pattern = re.compile(rf"{re.escape(version)}-rc\.(\d+)")
        for row in rows:
            match = rc_pattern.match(row["tag"])
            if match:
                rc_num = int(match.group(1))
                if rc_num > highest_rc:
                    highest_rc = rc_num

        return f"{version}-rc.{highest_rc + 1}"

    @staticmethod
    def start_evolution(
        data: SqliteData,
        version: str,
        change_id: str,
        auto_tag: bool = True,
        repo_path: Optional[Path] = None,
        created_by: Optional[str] = None,
    ) -> Evolution:
        """
        Start a new evolution for a generation change.

        This will:
        1. Validate the generation and change exist
        2. Generate the next RC tag
        3. Create the evolution record
        4. Optionally create a git tag

        Returns the created Evolution.
        """
        # Ensure version starts with 'v'
        if not version.startswith("v"):
            version = f"v{version}"

        # Find generation
        gen_rows = data.query(
            "SELECT generation_id FROM generations WHERE version = ?", (version,)
        )
        if not gen_rows:
            raise ValueError(f"Generation {version} not found")

        generation_id = gen_rows[0]["generation_id"]

        # Validate change belongs to generation
        change_rows = data.query(
            "SELECT change_id FROM generation_changes WHERE change_id = ? AND generation_id = ?",
            (change_id, generation_id),
        )
        if not change_rows:
            raise ValueError(f"Change {change_id} not found in generation {version}")

        # Generate next RC tag
        tag = Evolution.generate_next_rc_tag(data, version)

        # Create evolution
        evolution = Evolution(
            generation_id=generation_id,
            change_id=change_id,
            tag=tag,
            status="pending",
            created_by=created_by,
        )

        evolution.save_to_db(data)

        # Create git tag if requested
        if auto_tag:
            evolution.create_git_tag(repo_path)

        return evolution
