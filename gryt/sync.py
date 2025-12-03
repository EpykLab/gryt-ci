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

            # Handle nested response structure: response["data"]["generations"]
            if "data" in cloud_response and "generations" in cloud_response["data"]:
                cloud_gens = cloud_response["data"]["generations"]
            elif "generations" in cloud_response:
                cloud_gens = cloud_response["generations"]
            else:
                cloud_gens = []

            logger.info(f"Pulled {len(cloud_gens)} generations from cloud")
            for cloud_gen in cloud_gens:
                logger.info(f"  Generation {cloud_gen.get('version')}: {len(cloud_gen.get('changes', []))} changes")
                for change in cloud_gen.get("changes", []):
                    logger.info(f"    Change {change['id']}: pipeline={change.get('pipeline')}")

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

    def push(self, version: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
        """Push local changes to cloud

        Args:
            version: Specific version to push, or None for all pending
            force: Force push even if sync_status is 'synced'

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
            if force:
                # Force: push ALL generations
                gens = Generation.list_all(self.data)
                logger.info(f"Force push: syncing all {len(gens)} generations")
            else:
                # Normal: only push pending
                gens = self._get_pending_generations()

        for gen in gens:
            try:
                if gen.remote_id:
                    # Update existing
                    gen_dict = gen.to_dict()
                    logger.info(f"Syncing {gen.version}: {len(gen.changes)} changes")
                    for change in gen.changes:
                        logger.info(f"  Change {change.change_id}: pipeline={change.pipeline}")
                    self.client.update_generation(
                        gen.remote_id,
                        gen_dict
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
                    # No remote_id - check if version exists in cloud
                    logger.info(f"Generation {gen.version} has no remote_id, checking if it exists in cloud...")
                    existing_cloud_gen = None
                    try:
                        existing_cloud_gen = self.client.get_generation_by_version(gen.version)
                        logger.info(f"Found {gen.version} in cloud with id={existing_cloud_gen.get('id')}")
                    except Exception as lookup_error:
                        # Not found in cloud, we'll try to create below
                        logger.info(f"Generation {gen.version} not found in cloud: {lookup_error}")

                    if existing_cloud_gen:
                        # Version exists in cloud - link local to cloud and update
                        cloud_id = existing_cloud_gen["id"]

                        # Save remote_id to local
                        self.data.update(
                            "generations",
                            {
                                "remote_id": cloud_id,
                                "sync_status": "synced",
                                "last_synced_at": datetime.now()
                            },
                            "generation_id = ?",
                            (gen.generation_id,)
                        )

                        # Update cloud with latest local state
                        try:
                            self.client.update_generation(cloud_id, gen.to_dict())
                            result["updated"] += 1
                            logger.info(f"Linked and updated existing cloud generation {gen.version}")
                        except Exception as update_error:
                            result["errors"].append({
                                "version": gen.version,
                                "error": f"Failed to update cloud generation: {update_error}"
                            })
                            logger.error(f"Failed to update {gen.version}: {update_error}")
                            continue
                    else:
                        # Version doesn't exist in cloud - create new
                        try:
                            gen_dict = gen.to_dict()
                            logger.info(f"Creating {gen.version} in cloud: {len(gen.changes)} changes")
                            for change in gen.changes:
                                logger.info(f"  Change {change.change_id}: pipeline={change.pipeline}")
                            cloud_result = self.client.create_generation(gen_dict)

                            # Extract ID from nested response structure
                            if "data" in cloud_result and "id" in cloud_result["data"]:
                                cloud_id = cloud_result["data"]["id"]
                            elif "id" in cloud_result:
                                cloud_id = cloud_result["id"]
                            else:
                                raise ValueError(f"API response missing 'id' field: {cloud_result}")

                            # Save remote_id to local
                            self.data.update(
                                "generations",
                                {
                                    "remote_id": cloud_id,
                                    "sync_status": "synced",
                                    "last_synced_at": datetime.now()
                                },
                                "generation_id = ?",
                                (gen.generation_id,)
                            )
                            result["created"] += 1
                            logger.info(f"Created new cloud generation {gen.version}")
                        except Exception as create_error:
                            # Check if error is because it already exists
                            error_str = str(create_error)
                            if "already exists" in error_str.lower():
                                result["errors"].append({
                                    "version": gen.version,
                                    "error": f"API error: {create_error}. Run 'gryt sync pull' first to link local and cloud versions."
                                })
                            else:
                                result["errors"].append({
                                    "version": gen.version,
                                    "error": f"Failed to create: {create_error}"
                                })
                            logger.error(f"Failed to create {gen.version}: {create_error}")
                            continue

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
            "SELECT generation_id, remote_id FROM generations WHERE version = ?",
            (version,)
        )
        if not rows:
            result["errors"].append({
                "version": version,
                "error": "Generation not found"
            })
            return result

        gen_id = rows[0]["generation_id"]
        gen_remote_id = rows[0]["remote_id"]

        # Check if generation has been synced to cloud
        if not gen_remote_id:
            result["errors"].append({
                "version": version,
                "error": "Generation not synced to cloud yet. Run 'gryt sync push' first."
            })
            return result

        # Get cloud generation to find its DB id
        try:
            cloud_gen = self.client.get_generation_by_version(version)
            cloud_gen_db_id = cloud_gen["id"]  # This is the integer DB id
        except Exception as e:
            result["errors"].append({
                "version": version,
                "error": f"Failed to get cloud generation: {e}"
            })
            return result

        # Get evolutions for this generation
        evos = Evolution.list_for_generation(self.data, gen_id)

        for evo in evos:
            try:
                # Find the cloud change DB id by change_id
                cloud_change = None
                for change in cloud_gen.get("changes", []):
                    if change["id"] == evo.change_id:
                        cloud_change = change
                        break

                if not cloud_change:
                    result["errors"].append({
                        "code_name": evo.code_name,
                        "tag": evo.tag,
                        "error": f"Change {evo.change_id} not found in cloud generation"
                    })
                    continue

                # Push associated pipeline run if it exists
                if evo.pipeline_run_id:
                    # Get the generation's team_id for pipeline association
                    gen_row = self.data.query(
                        "SELECT team_id FROM generations WHERE generation_id = ?",
                        (gen_id,)
                    )
                    team_id = gen_row[0]["team_id"] if gen_row and gen_row[0].get("team_id") else None

                    pipeline_result = self.push_pipeline_run(evo.pipeline_run_id, team_id)
                    if not pipeline_result["success"]:
                        # Log warning but continue - pipeline push failure shouldn't block evolution sync
                        logger.warning(f"Failed to push pipeline {evo.pipeline_run_id} for evolution {evo.code_name}: {pipeline_result.get('error')}")

                # Get the cloud DB id for this change
                # We need to query the cloud API to get the change's internal DB id
                # For now, we'll use the change_id from the cloud generation response
                # The API expects the DB id, which we need to extract from the cloud response

                # Prepare evolution data with cloud DB IDs
                evo_data = {
                    "evolution_id": evo.evolution_id,
                    "generation_id": str(cloud_gen_db_id),  # Convert to string for Pydantic validation
                    "change_id": evo.change_id,  # String like "DB-001" - API will look it up
                    "code_name": evo.code_name,
                    "tag": evo.tag,
                    "status": evo.status,
                    "pipeline_run_id": evo.pipeline_run_id,
                    "created_by": evo.created_by,
                }

                if evo.remote_id:
                    # Update existing
                    update_data = {
                        "status": evo.status,
                        "pipeline_run_id": evo.pipeline_run_id,
                        "completed_at": evo.completed_at.isoformat() if evo.completed_at else None,
                    }
                    self.client.update_evolution(evo.remote_id, update_data)
                    result["updated"] += 1
                else:
                    # Create new
                    try:
                        cloud_result = self.client.create_evolution(evo_data)

                        # Extract the id from the nested data field
                        remote_id = cloud_result.get("data", {}).get("id") if isinstance(cloud_result, dict) else None
                        if not remote_id:
                            raise ValueError(f"Invalid API response: missing id in {cloud_result}")

                        # Save remote_id
                        self.data.update(
                            "evolutions",
                            {
                                "remote_id": str(remote_id),
                                "sync_status": "synced",
                                "last_synced_at": datetime.now()
                            },
                            "evolution_id = ?",
                            (evo.evolution_id,)
                        )
                        result["created"] += 1

                    except Exception as create_error:
                        # Check if it's a duplicate key error
                        error_str = str(create_error)
                        if "duplicate key" in error_str.lower() or "already exists" in error_str.lower():
                            # Evolution already exists in cloud, fetch it to get remote_id
                            try:
                                evolutions_list = self.client.list_evolutions(generation_id=str(cloud_gen_db_id))
                                cloud_evos = evolutions_list.get("data", {}).get("evolutions", [])

                                # Find matching evolution by evolution_id
                                matching_evo = None
                                for cloud_evo in cloud_evos:
                                    if cloud_evo.get("evolution_id") == evo.evolution_id:
                                        matching_evo = cloud_evo
                                        break

                                if matching_evo:
                                    # Save remote_id and update
                                    remote_id = matching_evo["id"]
                                    self.data.update(
                                        "evolutions",
                                        {
                                            "remote_id": str(remote_id),
                                            "sync_status": "synced",
                                            "last_synced_at": datetime.now()
                                        },
                                        "evolution_id = ?",
                                        (evo.evolution_id,)
                                    )

                                    # Now update it with latest data
                                    update_data = {
                                        "status": evo.status,
                                        "pipeline_run_id": evo.pipeline_run_id,
                                        "completed_at": evo.completed_at.isoformat() if evo.completed_at else None,
                                    }
                                    self.client.update_evolution(str(remote_id), update_data)
                                    result["updated"] += 1
                                else:
                                    raise create_error
                            except Exception:
                                # If we can't recover, re-raise original error
                                raise create_error
                        else:
                            # Not a duplicate error, re-raise
                            raise

            except Exception as e:
                result["errors"].append({
                    "code_name": evo.code_name,
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
                "code_name": evo["code_name"],
                "tag": evo.get("tag"),
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
            "team_id": cloud_gen.get("team_id"),
            "sync_status": "synced",
            "remote_id": cloud_gen["id"],
            "last_synced_at": datetime.now()
        })

        # Insert changes
        logger.info(f"Inserting {len(cloud_gen.get('changes', []))} changes from cloud")
        for change in cloud_gen.get("changes", []):
            logger.info(f"  Change {change['id']}: pipeline={change.get('pipeline')}")
            self.data.insert("generation_changes", {
                "change_id": change["id"],
                "generation_id": cloud_gen["generation_id"],
                "type": change["type"],
                "title": change["title"],
                "description": change.get("description"),
                "status": change.get("status", "pending"),
                "pipeline": change.get("pipeline")
            })

        # Fetch and insert evolutions
        self._pull_evolutions_for_generation(cloud_gen)

        logger.info(f"Inserted generation {cloud_gen['version']} from cloud")

    def _update_from_cloud(self, local_row: Dict[str, Any], cloud_gen: Dict[str, Any]) -> None:
        """Update local generation with cloud state"""
        generation_id = local_row["generation_id"]

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
                "team_id": cloud_gen.get("team_id"),
                "sync_status": "synced",
                "last_synced_at": datetime.now()
            },
            "generation_id = ?",
            (generation_id,)
        )

        # Update changes if provided
        if "changes" in cloud_gen:
            # IMPORTANT: Delete evolutions FIRST to avoid FK constraint issues
            # When we delete changes, CASCADE DELETE would delete evolutions anyway,
            # but deleting explicitly first allows us to re-insert from cloud properly
            self.data.conn.execute(
                "DELETE FROM evolutions WHERE generation_id = ?",
                (generation_id,)
            )
            self.data.conn.commit()

            # Delete existing changes
            self.data.conn.execute(
                "DELETE FROM generation_changes WHERE generation_id = ?",
                (generation_id,)
            )
            self.data.conn.commit()

            # Insert changes from cloud
            logger.info(f"Updating {len(cloud_gen.get('changes', []))} changes from cloud")
            for change in cloud_gen.get("changes", []):
                logger.info(f"  Change {change['id']}: pipeline={change.get('pipeline')}")
                self.data.insert("generation_changes", {
                    "change_id": change["id"],
                    "generation_id": generation_id,
                    "type": change["type"],
                    "title": change["title"],
                    "description": change.get("description"),
                    "status": change.get("status", "pending"),
                    "pipeline": change.get("pipeline")
                })

        # Fetch and update evolutions (pass local generation_id for FK consistency)
        self._pull_evolutions_for_generation(cloud_gen, generation_id)

        logger.info(f"Updated generation {cloud_gen['version']} from cloud with {len(cloud_gen.get('changes', []))} changes")

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

    def _pull_evolutions_for_generation(self, cloud_gen: Dict[str, Any], local_generation_id: Optional[str] = None) -> None:
        """Fetch and sync evolutions for a generation from cloud

        Args:
            cloud_gen: Cloud generation data
            local_generation_id: Local generation_id to use for FK (if None, uses cloud_gen["generation_id"])
        """
        try:
            # Use local generation_id if provided, otherwise fallback to cloud
            generation_id = local_generation_id or cloud_gen["generation_id"]

            # Fetch evolutions from cloud for this generation
            cloud_gen_db_id = cloud_gen["id"]  # This is the integer DB id
            evolutions_response = self.client.list_evolutions(generation_id=str(cloud_gen_db_id))

            # Extract evolutions from nested response structure
            if "data" in evolutions_response and "evolutions" in evolutions_response["data"]:
                cloud_evolutions = evolutions_response["data"]["evolutions"]
            elif "evolutions" in evolutions_response:
                cloud_evolutions = evolutions_response["evolutions"]
            else:
                cloud_evolutions = []

            logger.info(f"Pulled {len(cloud_evolutions)} evolutions for generation {cloud_gen['version']}")

            for cloud_evo in cloud_evolutions:
                # Check if evolution already exists locally by evolution_id
                local_evo = self.data.query(
                    "SELECT * FROM evolutions WHERE evolution_id = ?",
                    (cloud_evo["evolution_id"],)
                )

                # Check if pipeline exists locally, if not set to None
                # (pipelines are not synced, so they may not exist locally)
                pipeline_run_id = cloud_evo.get("pipeline_run_id")
                if pipeline_run_id:
                    pipeline_check = self.data.query(
                        "SELECT pipeline_id FROM pipelines WHERE pipeline_id = ?",
                        (pipeline_run_id,)
                    )
                    if not pipeline_check:
                        pipeline_run_id = None

                evolution_data = {
                    "evolution_id": cloud_evo["evolution_id"],
                    "generation_id": generation_id,  # Use consistent generation_id
                    "change_id": cloud_evo["change_id"],  # API now returns string change_id
                    "code_name": cloud_evo["code_name"],
                    "tag": cloud_evo.get("tag"),
                    "status": cloud_evo["status"],
                    "pipeline_run_id": pipeline_run_id,  # Use validated pipeline_run_id or None
                    "started_at": cloud_evo.get("started_at"),
                    "completed_at": cloud_evo.get("completed_at"),
                    "created_by": cloud_evo.get("created_by"),
                    "remote_id": str(cloud_evo["id"]),
                    "sync_status": "synced",
                    "last_synced_at": datetime.now()
                }

                if local_evo:
                    # Update existing evolution
                    self.data.update(
                        "evolutions",
                        evolution_data,
                        "evolution_id = ?",
                        (cloud_evo["evolution_id"],)
                    )
                    logger.info(f"  Updated evolution {cloud_evo['code_name']} from cloud")
                else:
                    # Insert new evolution
                    self.data.insert("evolutions", evolution_data)
                    logger.info(f"  Inserted evolution {cloud_evo['code_name']} from cloud")

                # Pull associated pipeline run if it exists
                if pipeline_run_id:
                    # Try to pull the pipeline run (if not already local)
                    pipeline_result = self.pull_pipeline_run(pipeline_run_id)
                    if not pipeline_result["success"] and pipeline_result["error"] != "Pipeline run not found in cloud":
                        logger.warning(f"  Failed to pull pipeline {pipeline_run_id} for evolution {cloud_evo['code_name']}: {pipeline_result.get('error')}")

        except Exception as e:
            logger.error(f"Failed to pull evolutions for generation {cloud_gen['version']}: {e}")

    def push_pipeline_run(self, pipeline_id: str, team_id: Optional[str] = None) -> Dict[str, Any]:
        """Push a pipeline run with all runners and step outputs to cloud

        Args:
            pipeline_id: The pipeline ID to push
            team_id: Optional team_id to associate with this pipeline run

        Returns:
            dict with keys: success, error
        """
        result = {"success": False, "error": None}

        try:
            # Get pipeline run from local DB
            pipeline_rows = self.data.query(
                "SELECT * FROM pipelines WHERE pipeline_id = ?",
                (pipeline_id,)
            )

            if not pipeline_rows:
                result["error"] = f"Pipeline {pipeline_id} not found locally"
                return result

            pipeline = pipeline_rows[0]

            # Get runners for this pipeline
            runners_rows = self.data.query(
                "SELECT * FROM runners WHERE pipeline_id = ? ORDER BY execution_order",
                (pipeline_id,)
            )

            # Build runners data and get step outputs
            runners_data = []
            step_outputs_data = []

            # If no runners exist, check if we have orphaned step outputs and create a synthetic runner
            if not runners_rows:
                orphaned_steps = self.data.query(
                    "SELECT * FROM steps_output WHERE runner_id IS NULL OR runner_id = '' ORDER BY timestamp",
                    ()
                )

                if orphaned_steps:
                    # Create a synthetic runner for orphaned steps
                    import uuid
                    synthetic_runner_id = f"{pipeline_id}-default-runner"

                    runners_data.append({
                        "runner_id": synthetic_runner_id,
                        "pipeline_id": pipeline_id,
                        "name": "Pipeline Steps",
                        "execution_order": 0,
                        "status": pipeline.get("status")
                    })

                    # Associate orphaned steps with the synthetic runner
                    for step_row in orphaned_steps:
                        import json
                        output_json = step_row.get("output_json")
                        if output_json and not isinstance(output_json, str):
                            output_json = json.dumps(output_json)

                        # Ensure stdout and stderr are strings (not dicts)
                        stdout = step_row.get("stdout")
                        if stdout and not isinstance(stdout, str):
                            stdout = json.dumps(stdout)

                        stderr = step_row.get("stderr")
                        if stderr and not isinstance(stderr, str):
                            stderr = json.dumps(stderr)

                        step_outputs_data.append({
                            "step_id": step_row.get("step_id"),
                            "runner_id": synthetic_runner_id,
                            "name": step_row.get("name"),
                            "output_json": output_json,
                            "stdout": stdout,
                            "stderr": stderr,
                            "status": step_row.get("status"),
                            "duration": step_row.get("duration"),
                            "timestamp": step_row.get("timestamp")
                        })

            for runner_row in runners_rows:
                runner_id = runner_row["runner_id"]
                runners_data.append({
                    "runner_id": runner_id,
                    "pipeline_id": pipeline_id,
                    "name": runner_row.get("name"),
                    "execution_order": runner_row.get("execution_order"),
                    "status": runner_row.get("status")
                })

                # Get step outputs for this runner
                steps_rows = self.data.query(
                    "SELECT * FROM steps_output WHERE runner_id = ? ORDER BY timestamp",
                    (runner_id,)
                )

                for step_row in steps_rows:
                    import json
                    output_json = step_row.get("output_json")
                    # Ensure output_json is a string
                    if output_json and not isinstance(output_json, str):
                        output_json = json.dumps(output_json)

                    # Ensure stdout and stderr are strings (not dicts)
                    stdout = step_row.get("stdout")
                    if stdout and not isinstance(stdout, str):
                        stdout = json.dumps(stdout)

                    stderr = step_row.get("stderr")
                    if stderr and not isinstance(stderr, str):
                        stderr = json.dumps(stderr)

                    step_outputs_data.append({
                        "step_id": step_row.get("step_id"),
                        "runner_id": runner_id,
                        "name": step_row.get("name"),
                        "output_json": output_json,
                        "stdout": stdout,
                        "stderr": stderr,
                        "status": step_row.get("status"),
                        "duration": step_row.get("duration"),
                        "timestamp": step_row.get("timestamp")
                    })

            # Build the batch request
            import json
            config_json = pipeline.get("config_json")
            # Ensure config_json is a string
            if config_json and not isinstance(config_json, str):
                config_json = json.dumps(config_json)

            batch_data = {
                "pipeline_run": {
                    "pipeline_id": pipeline_id,
                    "name": pipeline.get("name"),
                    "start_timestamp": pipeline.get("start_timestamp"),
                    "end_timestamp": pipeline.get("end_timestamp"),
                    "status": pipeline.get("status"),
                    "config_json": config_json,
                    "team_id": team_id
                },
                "runners": runners_data,
                "step_outputs": step_outputs_data
            }

            # Push to cloud
            try:
                cloud_result = self.client.create_pipeline_run(batch_data)

                if "data" in cloud_result:
                    result["success"] = True
                    logger.info(f"Pushed pipeline run {pipeline_id} to cloud with {len(runners_data)} runners and {len(step_outputs_data)} steps")
                else:
                    result["error"] = f"Unexpected API response: {cloud_result}"
            except Exception as create_error:
                error_str = str(create_error)
                # If it's a duplicate key error, just log and treat as success
                if "duplicate key" in error_str.lower() or "already exists" in error_str.lower() or "UniqueViolation" in error_str:
                    logger.info(f"Pipeline run {pipeline_id} already exists in cloud, skipping")
                    result["success"] = True
                else:
                    # Real error, re-raise
                    raise

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Failed to push pipeline run {pipeline_id}: {e}")

        return result

    def pull_pipeline_run(self, pipeline_id: str) -> Dict[str, Any]:
        """Pull a pipeline run from cloud and sync to local DB

        Args:
            pipeline_id: The pipeline ID to pull

        Returns:
            dict with keys: success, error
        """
        result = {"success": False, "error": None}

        try:
            # Fetch from cloud
            cloud_result = self.client.get_pipeline_run(pipeline_id)

            if "data" not in cloud_result:
                result["error"] = "Pipeline run not found in cloud"
                return result

            pipeline_data = cloud_result["data"]

            # Check if pipeline already exists locally
            existing = self.data.query(
                "SELECT pipeline_id FROM pipelines WHERE pipeline_id = ?",
                (pipeline_id,)
            )

            if existing:
                # Already exists, skip
                logger.info(f"Pipeline {pipeline_id} already exists locally, skipping")
                result["success"] = True
                return result

            # Insert pipeline
            self.data.insert("pipelines", {
                "pipeline_id": pipeline_data["pipeline_id"],
                "name": pipeline_data.get("name"),
                "start_timestamp": pipeline_data.get("start_timestamp"),
                "end_timestamp": pipeline_data.get("end_timestamp"),
                "status": pipeline_data.get("status"),
                "config_json": pipeline_data.get("config_json")
            })

            # Insert runners and steps
            for runner_data in pipeline_data.get("runners", []):
                self.data.insert("runners", {
                    "runner_id": runner_data["runner_id"],
                    "pipeline_id": pipeline_id,
                    "name": runner_data.get("name"),
                    "execution_order": runner_data.get("execution_order"),
                    "status": runner_data.get("status")
                })

                # Insert step outputs
                for step_data in runner_data.get("steps", []):
                    self.data.insert("steps_output", {
                        "step_id": step_data.get("step_id"),
                        "runner_id": runner_data["runner_id"],
                        "name": step_data.get("name"),
                        "output_json": step_data.get("output_json"),
                        "stdout": step_data.get("stdout"),
                        "stderr": step_data.get("stderr"),
                        "status": step_data.get("status"),
                        "duration": step_data.get("duration"),
                        "timestamp": step_data.get("timestamp")
                    })

            result["success"] = True
            logger.info(f"Pulled pipeline run {pipeline_id} from cloud")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Failed to pull pipeline run {pipeline_id}: {e}")

        return result


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
