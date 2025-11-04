"""
Generation contract system (v0.2.0)

A Generation is a release contract that declares what a version MUST contain.
"""
from __future__ import annotations

import json
import subprocess
import uuid
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from .data import SqliteData
from .events import get_event_bus


class GenerationChange:
    """A single change within a Generation (Fix/Refine/Add/Remove)"""

    def __init__(
        self,
        change_id: str,
        change_type: str,
        title: str,
        description: Optional[str] = None,
        status: str = "pending",
        pipeline: Optional[str] = None,
        pipelines: Optional[List[Dict[str, Any]]] = None,
    ):
        self.change_id = change_id
        self.type = change_type
        self.title = title
        self.description = description
        self.status = status
        self.pipeline = pipeline
        self.pipelines = pipelines or []

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.change_id,
            "type": self.type,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "pipeline": self.pipeline,  # Legacy field - backward compatibility
        }

        # Include pipelines array if there are any
        if self.pipelines:
            result["pipelines"] = self.pipelines

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GenerationChange:
        return cls(
            change_id=data["id"],
            change_type=data["type"],
            title=data["title"],
            description=data.get("description"),
            status=data.get("status", "pending"),
            pipeline=data.get("pipeline"),
        )


class Generation:
    """
    A Generation is a release contract defining what vX.Y.Z must contain.

    Attributes:
        generation_id: Unique identifier
        version: SemVer version string (e.g., "v2.2.0")
        description: Human-readable description
        changes: List of GenerationChange objects
        pipeline_template: Pipeline to use for evolutions
        status: draft|active|promoted|abandoned
        sync_status: not_synced|syncing|synced|conflict
        remote_id: ID in cloud (if synced)
        team_id: ID of team generation will be linked to
    """

    def __init__(
        self,
        version: str,
        changes: List[GenerationChange],
        description: Optional[str] = None,
        pipeline_template: Optional[str] = None,
        generation_id: Optional[str] = None,
        status: str = "draft",
        sync_status: str = "not_synced",
        remote_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
        promoted_at: Optional[datetime] = None,
        created_by: Optional[str] = None,
        promoted_by: Optional[str] = None,
        team_id: Optional[str] = None,
    ):
        self.generation_id = generation_id or str(uuid.uuid4())
        self.version = version if version.startswith("v") else f"v{version}"
        self.description = description
        self.changes = changes
        self.pipeline_template = pipeline_template
        self.status = status
        self.sync_status = sync_status
        self.created_by = created_by
        self.promoted_by = promoted_by
        self.team_id = team_id
        self.remote_id = remote_id
        self.created_at = created_at or datetime.now()
        self.promoted_at = promoted_at

    @classmethod
    def from_yaml_file(cls, yaml_path: Path) -> Generation:
        """Load a Generation from a YAML file"""
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)

        # Validate against JSON schema
        cls._validate_schema(data)

        changes = [GenerationChange.from_dict(c) for c in data["changes"]]
        return cls(
            version=data["version"],
            description=data.get("description"),
            changes=changes,
            pipeline_template=data.get("pipeline_template"),
        )

    @classmethod
    def from_db(cls, data: SqliteData, generation_id: str) -> Optional[Generation]:
        """Load a Generation from the database"""
        from datetime import datetime

        rows = data.query(
            "SELECT * FROM generations WHERE generation_id = ?", (generation_id,)
        )
        if not rows:
            return None

        row = rows[0]
        changes_rows = data.query(
            "SELECT * FROM generation_changes WHERE generation_id = ? ORDER BY created_at",
            (generation_id,),
        )

        # Debug: Log what we're loading from DB
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Loading {len(changes_rows)} changes for generation {generation_id}")
        for c in changes_rows:
            logger.info(f"  DB row: change_id={c['change_id']}, pipeline={c.get('pipeline')}")

        changes = []
        for c in changes_rows:
            # Load linked pipelines from change_pipelines table
            pipelines_rows = data.query(
                "SELECT pipeline_name, is_primary, created_by, created_at FROM change_pipelines WHERE change_id = ? AND generation_id = ? ORDER BY is_primary DESC, pipeline_name",
                (c["change_id"], generation_id),
            )

            pipelines_list = [
                {
                    "pipeline_name": p["pipeline_name"],
                    "is_primary": bool(p["is_primary"]),
                    "created_by": p.get("created_by"),
                }
                for p in pipelines_rows
            ]

            changes.append(
                GenerationChange(
                    change_id=c["change_id"],
                    change_type=c["type"],
                    title=c["title"],
                    description=c.get("description"),
                    status=c["status"],
                    pipeline=c.get("pipeline"),
                    pipelines=pipelines_list if pipelines_list else None,
                )
            )

        # Debug: Log what GenerationChange objects have
        for change in changes:
            logger.info(f"  GenerationChange object: {change.change_id}, pipeline={change.pipeline}, pipelines={len(change.pipelines)} linked")

        # Parse datetime strings from DB
        created_at = row.get("created_at")
        if created_at and isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                created_at = None

        promoted_at = row.get("promoted_at")
        if promoted_at and isinstance(promoted_at, str):
            try:
                promoted_at = datetime.fromisoformat(promoted_at.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                promoted_at = None

        return cls(
            generation_id=row["generation_id"],
            version=row["version"],
            description=row.get("description"),
            changes=changes,
            pipeline_template=row.get("pipeline_template"),
            status=row["status"],
            sync_status=row.get("sync_status", "not_synced"),
            remote_id=row.get("remote_id"),
            created_at=created_at,
            promoted_at=promoted_at,
            created_by=row.get("created_by"),
            promoted_by=row.get("promoted_by"),
            team_id=row.get("team_id"),
        )

    def save_to_db(self, data: SqliteData, emit_event: bool = True) -> None:
        """Save this Generation to the database"""
        # Check if exists
        existing = data.query(
            "SELECT generation_id FROM generations WHERE generation_id = ?",
            (self.generation_id,),
        )

        is_new = not existing

        gen_dict = {
            "generation_id": self.generation_id,
            "version": self.version,
            "description": self.description,
            "status": self.status,
            "pipeline_template": self.pipeline_template,
            "sync_status": self.sync_status,
            "remote_id": self.remote_id,
            "promoted_at": self.promoted_at,
            "created_by": self.created_by,
            "promoted_by": self.promoted_by,
            "team_id": self.team_id,
        }

        if existing:
            # Update
            data.update(
                "generations",
                gen_dict,
                "generation_id = ?",
                (self.generation_id,),
            )
        else:
            # Insert
            gen_dict["created_at"] = self.created_at
            data.insert("generations", gen_dict)

        # Save changes
        for change in self.changes:
            change_dict = {
                "change_id": change.change_id,
                "generation_id": self.generation_id,
                "type": change.type,
                "title": change.title,
                "description": change.description,
                "status": change.status,
                "pipeline": change.pipeline,
            }
            existing_change = data.query(
                "SELECT change_id FROM generation_changes WHERE change_id = ?",
                (change.change_id,),
            )
            if not existing_change:
                data.insert("generation_changes", change_dict)

        # Emit event
        if emit_event:
            bus = get_event_bus()
            event_name = "generation.created" if is_new else "generation.updated"
            bus.emit(event_name, {"generation": self.to_dict()})

    def save_to_yaml(self, generations_dir: Path) -> Path:
        """Save this Generation to a YAML file"""
        yaml_path = generations_dir / f"{self.version}.yaml"
        yaml_data = {
            "version": self.version,
            "description": self.description,
            "changes": [c.to_dict() for c in self.changes],
        }
        if self.pipeline_template:
            yaml_data["pipeline_template"] = self.pipeline_template

        with open(yaml_path, "w") as f:
            yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

        return yaml_path

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "generation_id": self.generation_id,
            "version": self.version,
            "description": self.description,
            "changes": [c.to_dict() for c in self.changes],
            "pipeline_template": self.pipeline_template,
            "status": self.status,
            "sync_status": self.sync_status,
            "remote_id": self.remote_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "promoted_at": self.promoted_at.isoformat() if self.promoted_at else None,
            "team_id": self.team_id,
        }

    @staticmethod
    def _validate_schema(data: Dict[str, Any]) -> None:
        """Validate Generation YAML against JSON schema"""
        try:
            import jsonschema
        except ImportError:
            # If jsonschema not available, skip validation
            return

        schema_path = Path(__file__).parent / "schemas" / "generation.json"
        if not schema_path.exists():
            return

        with open(schema_path, "r") as f:
            schema = json.load(f)

        jsonschema.validate(data, schema)

    @staticmethod
    def list_all(data: SqliteData) -> List[Generation]:
        """List all generations from database"""
        rows = data.query("SELECT generation_id FROM generations ORDER BY created_at DESC")
        return [Generation.from_db(data, row["generation_id"]) for row in rows if Generation.from_db(data, row["generation_id"])]

    def promote(
        self,
        data: SqliteData,
        gates: Optional[List["PromotionGate"]] = None,
        auto_tag: bool = True,
        repo_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Promote this generation to production.

        This will:
        1. Run all promotion gates
        2. If all pass, create final version tag (vX.Y.Z)
        3. Update status to 'promoted'
        4. Emit generation.promoted event

        Returns a dict with:
            - success: bool
            - message: str
            - gate_results: List[GateResult]
            - tag: str (if successful)
        """
        from .gates import get_default_gates

        # Use default gates if none provided
        if gates is None:
            gates = get_default_gates()

        # Run all gates
        gate_results = []
        all_passed = True

        for gate in gates:
            result = gate.check(self, data)
            gate_results.append({
                "gate": gate.name,
                "passed": result.passed,
                "message": result.message,
                "details": result.details
            })
            if not result.passed:
                all_passed = False

        if not all_passed:
            failed_gates = [r for r in gate_results if not r["passed"]]
            return {
                "success": False,
                "message": f"{len(failed_gates)} promotion gate(s) failed",
                "gate_results": gate_results
            }

        # All gates passed - promote!
        self.status = "promoted"
        self.promoted_at = datetime.now()

        # Set promoted_by from config
        try:
            from .config import Config
            config = Config.load_with_repo_context()
            self.promoted_by = config.username or "unknown"
        except:
            self.promoted_by = "unknown"

        self.save_to_db(data, emit_event=False)  # Don't emit yet

        # Create final version tag
        tag_created = False
        if auto_tag:
            tag_created = self._create_final_tag(repo_path)

        # Emit promotion event
        bus = get_event_bus()
        bus.emit("generation.promoted", {"generation": self.to_dict()})

        return {
            "success": True,
            "message": f"Generation {self.version} promoted successfully",
            "gate_results": gate_results,
            "tag": self.version if tag_created else None,
            "tag_created": tag_created
        }

    def _create_final_tag(self, repo_path: Optional[Path] = None) -> bool:
        """
        Create final version tag (vX.Y.Z) for this generation.

        Returns True if successful, False otherwise.
        """
        repo = repo_path or Path.cwd()
        try:
            # Create annotated tag
            change_summary = "\n".join([f"- [{c.type}] {c.title}" for c in self.changes])
            message = f"Release {self.version}\n\n{self.description or ''}\n\nChanges:\n{change_summary}"

            subprocess.run(
                ["git", "tag", "-a", self.version, "-m", message],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False
