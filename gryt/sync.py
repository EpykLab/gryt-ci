"""
Bidirectional Cloud Sync (v1.0.0)

Handles syncing generations and evolutions between local SQLite and Gryt Cloud.
Implements version-based locking to prevent conflicts in distributed teams.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from .data import SqliteData
from .cloud_client import GrytCloudClient
from .generation import Generation
from .evolution import Evolution
from .events import Event, EventBus, get_event_bus


logger = logging.getLogger(__name__)


class CloudSync:
    """Bidirectional sync with conflict detection"""

    def __init__(self, data: SqliteData, client: GrytCloudClient):
        self.data = data
        self.client = client

    def pull(self) -> Dict[str, Any]:
        """Pull cloud state to local

        Returns:
            dict with keys: new, updated, conflicts
        """
        result = {
            "new": 0,
            "updated": 0,
            "conflicts": []
        }

        try:
            # Fetch all cloud generations
            cloud_response = self.client.list_generations()
            cloud_gens = cloud_response.get("generations", [])

            for cloud_gen in cloud_gens:
                remote_id = cloud_gen["id"]
                version = cloud_gen["version"]

                # Check if exists locally by remote_id
                local = self.data.query(
                    "SELECT * FROM generations WHERE remote_id = ?",
                    (remote_id,)
                )

                if not local:
                    # Check if same version exists locally without remote_id
                    local_by_version = self.data.query(
                        "SELECT * FROM generations WHERE version = ?",
                        (version,)
                    )

                    if local_by_version:
                        # Conflict: same version, different source
                        result["conflicts"].append({
                            "version": version,
                            "reason": "Local and cloud have same version",
                            "resolution": "Rename local version or delete"
                        })
                    else:
                        # New from cloud, insert
                        self._insert_from_cloud(cloud_gen)
                        result["new"] += 1
                else:
                    # Update local with cloud state
                    self._update_from_cloud(local[0], cloud_gen)
                    result["updated"] += 1

            # Update last pull timestamp
            self._set_metadata("last_pull_timestamp", datetime.now().isoformat())

            logger.info(f"Pull complete: {result['new']} new, {result['updated']} updated")

        except Exception as e:
            logger.error(f"Pull failed: {e}")
            raise

        return result

    def push(self, version: Optional[str] = None) -> Dict[str, Any]:
        """Push local changes to cloud

        Args:
            version: Specific version to push, or None for all pending

        Returns:
            dict with keys: created, updated, errors
        """
        result = {
            "created": 0,
            "updated": 0,
            "errors": []
        }

        # Get generations to sync
        if version:
            rows = self.data.query(
                "SELECT generation_id FROM generations WHERE version = ?",
                (version,)
            )
            if not rows:
                result["errors"].append({
                    "version": version,
                    "error": "Generation not found locally"
                })
                return result
            gens = [Generation.from_db(self.data, rows[0]["generation_id"])]
        else:
            # All not synced or modified
            gens = self._get_pending_generations()

        for gen in gens:
            try:
                if gen.remote_id:
                    # Update existing
                    self.client.update_generation(
                        gen.remote_id,
                        gen.to_dict()
                    )

                    # Update sync status
                    self.data.update(
                        "generations",
                        {
                            "sync_status": "synced",
                            "last_synced_at": datetime.now()
                        },
                        "generation_id = ?",
                        (gen.generation_id,)
                    )
                    result["updated"] += 1
                else:
                    # Check if version exists in cloud
                    conflict = self._check_version_conflict(gen.version)
                    if conflict:
                        result["errors"].append({
                            "version": gen.version,
                            "error": f"Version {gen.version} already exists in cloud",
                            "resolution": "Use different version or pull to sync"
                        })
                        continue

                    # Create new
                    cloud_result = self.client.create_generation(gen.to_dict())

                    # Save remote_id to local
                    self.data.update(
                        "generations",
                        {
                            "remote_id": cloud_result["id"],
                            "sync_status": "synced",
                            "last_synced_at": datetime.now()
                        },
                        "generation_id = ?",
                        (gen.generation_id,)
                    )
                    result["created"] += 1

                logger.info(f"Pushed generation {gen.version} to cloud")

            except Exception as e:
                error_msg = str(e)
                result["errors"].append({
                    "version": gen.version,
                    "error": error_msg
                })

                # Update sync status to failed
                self.data.update(
                    "generations",
                    {
                        "sync_status": "failed"
                    },
                    "generation_id = ?",
                    (gen.generation_id,)
                )

                logger.error(f"Failed to push {gen.version}: {error_msg}")

        return result

    def push_evolutions(self, version: str) -> Dict[str, Any]:
        """Push evolutions for a specific generation

        Args:
            version: Generation version

        Returns:
            dict with keys: created, updated, errors
        """
        result = {
            "created": 0,
            "updated": 0,
            "errors": []
        }

        # Get generation
        rows = self.data.query(
            "SELECT generation_id FROM generations WHERE version = ?",
            (version,)
        )
        if not rows:
            result["errors"].append({
                "version": version,
                "error": "Generation not found"
            })
            return result

        gen_id = rows[0]["generation_id"]

        # Get evolutions for this generation
        evos = Evolution.list_for_generation(self.data, gen_id)

        for evo in evos:
            try:
                if evo.remote_id:
                    # Update existing
                    self.client.update_evolution(
                        evo.remote_id,
                        evo.to_dict()
                    )
                    result["updated"] += 1
                else:
                    # Create new
                    cloud_result = self.client.create_evolution(evo.to_dict())

                    # Save remote_id
                    self.data.update(
                        "evolutions",
                        {
                            "remote_id": cloud_result["id"],
                            "sync_status": "synced",
                            "last_synced_at": datetime.now()
                        },
                        "evolution_id = ?",
                        (evo.evolution_id,)
                    )
                    result["created"] += 1

            except Exception as e:
                result["errors"].append({
                    "tag": evo.tag,
                    "error": str(e)
                })

        return result

    def status(self, version: Optional[str] = None) -> Dict[str, Any]:
        """Get sync status

        Args:
            version: Specific version or None for all

        Returns:
            Sync status information
        """
        if version:
            return self._status_for_version(version)
        else:
            return self._status_all()

    def _status_all(self) -> Dict[str, Any]:
        """Overall sync status"""
        local_gens = Generation.list_all(self.data)

        synced_count = sum(1 for g in local_gens if g.sync_status == "synced")
        pending_count = sum(1 for g in local_gens if g.sync_status in ("not_synced", "syncing"))
        conflict_count = sum(1 for g in local_gens if g.sync_status == "conflict")

        # Build generation list
        generations = []
        for gen in local_gens:
            gen_row = self.data.query(
                "SELECT * FROM generations WHERE generation_id = ?",
                (gen.generation_id,)
            )[0]
            generations.append({
                "version": gen.version,
                "sync_status": gen.sync_status or "not_synced",
                "remote_id": gen.remote_id,
                "last_synced_at": gen_row.get("last_synced_at"),
            })

        return {
            "summary": {
                "total": len(local_gens),
                "synced": synced_count,
                "pending": pending_count,
                "conflicts": conflict_count,
            },
            "generations": generations
        }

    def _status_for_version(self, version: str) -> Dict[str, Any]:
        """Status for specific version"""
        rows = self.data.query(
            "SELECT * FROM generations WHERE version = ?",
            (version,)
        )

        if not rows:
            return {
                "generation": {
                    "version": version,
                    "sync_status": "not_found",
                    "remote_id": None,
                    "last_synced_at": None,
                    "evolutions": []
                }
            }

        gen_row = rows[0]
        gen = Generation.from_db(self.data, gen_row["generation_id"])

        # Get evolutions
        evo_rows = self.data.query(
            "SELECT * FROM evolutions WHERE generation_id = ?",
            (gen_row["generation_id"],)
        )
        evolutions = [
            {
                "tag": evo["tag"],
                "sync_status": evo.get("sync_status", "not_synced"),
                "remote_id": evo.get("remote_id"),
            }
            for evo in evo_rows
        ]

        return {
            "generation": {
                "version": gen.version,
                "sync_status": gen.sync_status or "not_synced",
                "remote_id": gen.remote_id,
                "last_synced_at": gen_row.get("last_synced_at"),
                "evolutions": evolutions
            }
        }

    def _detect_conflicts(self) -> List[Dict[str, Any]]:
        """Detect sync conflicts"""
        conflicts = []

        local_gens = Generation.list_all(self.data)

        for gen in local_gens:
            if not gen.remote_id and gen.sync_status == "not_synced":
                # Check if version exists in cloud
                try:
                    self.client.get_generation_by_version(gen.version)
                    conflicts.append({
                        "version": gen.version,
                        "type": "version_exists",
                        "message": f"Version {gen.version} exists in cloud but not linked locally"
                    })
                except:
                    pass  # No conflict

        return conflicts

    def _check_version_conflict(self, version: str) -> bool:
        """Check if version exists in cloud

        Returns:
            True if conflict exists
        """
        try:
            self.client.get_generation_by_version(version)
            return True
        except:
            return False

    def _get_pending_generations(self) -> List[Generation]:
        """Get all generations pending sync"""
        rows = self.data.query("""
            SELECT generation_id FROM generations
            WHERE sync_status != 'synced'
            ORDER BY created_at
        """)

        gens = []
        for row in rows:
            gen = Generation.from_db(self.data, row["generation_id"])
            if gen:
                gens.append(gen)

        return gens

    def _insert_from_cloud(self, cloud_gen: Dict[str, Any]) -> None:
        """Insert generation from cloud data"""
        # Insert generation
        self.data.insert("generations", {
            "generation_id": cloud_gen["generation_id"],
            "version": cloud_gen["version"],
            "description": cloud_gen.get("description"),
            "status": cloud_gen.get("status", "draft"),
            "pipeline_template": cloud_gen.get("pipeline_template"),
            "created_at": cloud_gen.get("created_at"),
            "promoted_at": cloud_gen.get("promoted_at"),
            "created_by": cloud_gen.get("created_by"),
            "promoted_by": cloud_gen.get("promoted_by"),
            "sync_status": "synced",
            "remote_id": cloud_gen["id"],
            "last_synced_at": datetime.now()
        })

        # Insert changes
        for change in cloud_gen.get("changes", []):
            self.data.insert("generation_changes", {
                "change_id": change["id"],
                "generation_id": cloud_gen["generation_id"],
                "type": change["type"],
                "title": change["title"],
                "description": change.get("description"),
                "status": change.get("status", "pending")
            })

        logger.info(f"Inserted generation {cloud_gen['version']} from cloud")

    def _update_from_cloud(self, local_row: Dict[str, Any], cloud_gen: Dict[str, Any]) -> None:
        """Update local generation with cloud state"""
        self.data.update(
            "generations",
            {
                "version": cloud_gen["version"],
                "description": cloud_gen.get("description"),
                "status": cloud_gen.get("status", "draft"),
                "pipeline_template": cloud_gen.get("pipeline_template"),
                "promoted_at": cloud_gen.get("promoted_at"),
                "created_by": cloud_gen.get("created_by"),
                "promoted_by": cloud_gen.get("promoted_by"),
                "sync_status": "synced",
                "last_synced_at": datetime.now()
            },
            "generation_id = ?",
            (local_row["generation_id"],)
        )

        logger.info(f"Updated generation {cloud_gen['version']} from cloud")

    def _set_metadata(self, key: str, value: str) -> None:
        """Set sync metadata value"""
        existing = self.data.query(
            "SELECT key FROM sync_metadata WHERE key = ?",
            (key,)
        )

        if existing:
            self.data.update(
                "sync_metadata",
                {"value": value, "updated_at": datetime.now()},
                "key = ?",
                (key,)
            )
        else:
            self.data.insert("sync_metadata", {
                "key": key,
                "value": value
            })

    def _get_metadata(self, key: str) -> Optional[str]:
        """Get sync metadata value"""
        rows = self.data.query(
            "SELECT value FROM sync_metadata WHERE key = ?",
            (key,)
        )
        return rows[0]["value"] if rows else None


class CloudSyncHandler:
    """
    Event-driven sync handler.

    Execution modes:
        - local: No auto-sync, manual sync only
        - cloud: Auto-sync on every generation/evolution change
        - hybrid: Sync on promote only (default)
    """

    def __init__(
        self,
        client: Optional[GrytCloudClient] = None,
        data: Optional[SqliteData] = None,
        execution_mode: str = "hybrid",
    ):
        self.client = client
        self.data = data
        self.execution_mode = execution_mode
        self._subscribed = False
        self._sync: Optional[CloudSync] = None

        if client and data:
            self._sync = CloudSync(data, client)

    def attach(self, bus: Optional[EventBus] = None) -> None:
        """Attach handler to event bus"""
        if self._subscribed:
            return

        event_bus = bus or get_event_bus()

        # Subscribe to generation events
        event_bus.subscribe("generation.created", self._on_generation_created)
        event_bus.subscribe("generation.updated", self._on_generation_updated)
        event_bus.subscribe("generation.promoted", self._on_generation_promoted)

        # Subscribe to evolution events
        event_bus.subscribe("evolution.created", self._on_evolution_created)
        event_bus.subscribe("evolution.completed", self._on_evolution_completed)
        event_bus.subscribe("evolution.failed", self._on_evolution_failed)

        self._subscribed = True
        logger.debug(f"CloudSyncHandler attached (mode: {self.execution_mode})")

    def detach(self, bus: Optional[EventBus] = None) -> None:
        """Detach handler from event bus"""
        if not self._subscribed:
            return

        event_bus = bus or get_event_bus()

        event_bus.unsubscribe("generation.created", self._on_generation_created)
        event_bus.unsubscribe("generation.updated", self._on_generation_updated)
        event_bus.unsubscribe("generation.promoted", self._on_generation_promoted)
        event_bus.unsubscribe("evolution.created", self._on_evolution_created)
        event_bus.unsubscribe("evolution.completed", self._on_evolution_completed)
        event_bus.unsubscribe("evolution.failed", self._on_evolution_failed)

        self._subscribed = False
        logger.debug("CloudSyncHandler detached")

    def _on_generation_created(self, event: Event) -> None:
        """Handle generation.created event"""
        if self.execution_mode == "cloud":
            self._sync_generation(event.payload["generation"])

    def _on_generation_updated(self, event: Event) -> None:
        """Handle generation.updated event"""
        if self.execution_mode == "cloud":
            self._sync_generation(event.payload["generation"])

    def _on_generation_promoted(self, event: Event) -> None:
        """Handle generation.promoted event"""
        if self.execution_mode in ("cloud", "hybrid"):
            self._sync_generation(event.payload["generation"])

    def _on_evolution_created(self, event: Event) -> None:
        """Handle evolution.created event"""
        if self.execution_mode == "cloud":
            self._sync_evolution(event.payload["evolution"])

    def _on_evolution_completed(self, event: Event) -> None:
        """Handle evolution.completed event"""
        if self.execution_mode in ("cloud", "hybrid"):
            self._sync_evolution(event.payload["evolution"])

    def _on_evolution_failed(self, event: Event) -> None:
        """Handle evolution.failed event"""
        if self.execution_mode in ("cloud", "hybrid"):
            self._sync_evolution(event.payload["evolution"])

    def _sync_generation(self, generation_data) -> None:
        """Sync a generation to cloud

        Args:
            generation_data: Either a Generation object or a dict with generation data
        """
        if not self._sync:
            logger.debug("No sync client configured, skipping")
            return

        try:
            # Handle both Generation object and dict
            if hasattr(generation_data, 'version'):
                version = generation_data.version
            else:
                version = generation_data.get("version")

            if version:
                result = self._sync.push(version)
                if result["errors"]:
                    logger.error(f"Sync errors for {version}: {result['errors']}")

        except Exception as e:
            logger.error(f"Failed to sync generation: {e}")

    def _sync_evolution(self, evolution_data: dict) -> None:
        """Sync an evolution to cloud"""
        if not self._sync:
            logger.debug("No sync client configured, skipping")
            return

        try:
            # Evolutions sync via their generation
            generation_id = evolution_data.get("generation_id")
            if generation_id and self.data:
                rows = self.data.query(
                    "SELECT version FROM generations WHERE generation_id = ?",
                    (generation_id,)
                )
                if rows:
                    self._sync.push_evolutions(rows[0]["version"])

        except Exception as e:
            logger.error(f"Failed to sync evolution: {e}")


def get_cloud_sync_handler(config_path: Optional[Path] = None) -> Optional[CloudSyncHandler]:
    """
    Get a CloudSyncHandler from config.

    Returns None if cloud sync is not configured.
    """
    from .config import Config

    try:
        config = Config.load_with_repo_context()

        if not config.has_credentials():
            return None

        client = GrytCloudClient(
            username=config.username,
            password=config.password,
            api_key_id=config.api_key_id,
            api_key_secret=config.api_key_secret,
            gryt_url=config.gryt_url
        )

        # Get execution mode
        execution_mode = config.get("execution_mode", "hybrid")

        # Get database path
        from .paths import get_repo_db_path

        db_path = get_repo_db_path()
        if not db_path or not db_path.exists():
            return None

        data = SqliteData(db_path=str(db_path))

        return CloudSyncHandler(
            client=client,
            data=data,
            execution_mode=execution_mode
        )

    except Exception as e:
        logger.error(f"Failed to create CloudSyncHandler: {e}")
        return None
