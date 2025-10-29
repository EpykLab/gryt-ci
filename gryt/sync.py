"""
CloudSyncHandler for syncing generations to gryt-cloud (v0.2.0)

Listens to generation lifecycle events and syncs to cloud API based on execution_mode.
"""
from __future__ import annotations

import logging
from typing import Optional
from pathlib import Path

from .events import Event, EventBus, get_event_bus
from .cloud_client import GrytCloudClient


logger = logging.getLogger(__name__)


class CloudSyncHandler:
    """
    Handles syncing generations to gryt-cloud.

    Execution modes:
        - local: No auto-sync, manual sync only
        - cloud: Auto-sync on every generation/evolution change
        - hybrid: Sync on promote only (default)
    """

    def __init__(
        self,
        client: Optional[GrytCloudClient] = None,
        execution_mode: str = "hybrid",
    ):
        self.client = client
        self.execution_mode = execution_mode
        self._subscribed = False

    def attach(self, bus: Optional[EventBus] = None) -> None:
        """Attach handler to event bus"""
        if self._subscribed:
            return

        event_bus = bus or get_event_bus()

        # Subscribe to generation events
        event_bus.subscribe("generation.created", self._on_generation_created)
        event_bus.subscribe("generation.updated", self._on_generation_updated)
        event_bus.subscribe("generation.promoted", self._on_generation_promoted)

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

    def _sync_generation(self, generation_data: dict) -> None:
        """Sync a generation to cloud"""
        if not self.client:
            logger.debug("No cloud client configured, skipping sync")
            return

        try:
            generation_id = generation_data["generation_id"]
            remote_id = generation_data.get("remote_id")

            if remote_id:
                # Update existing
                logger.info(f"Syncing generation {generation_data['version']} (update)")
                self.client.update_generation(remote_id, generation_data)
            else:
                # Create new
                logger.info(f"Syncing generation {generation_data['version']} (create)")
                result = self.client.create_generation(generation_data)
                # TODO: Update local DB with remote_id from result
                logger.debug(f"Created generation in cloud: {result}")

        except Exception as e:
            logger.error(f"Failed to sync generation: {e}")
            # TODO: Update sync_status to 'failed' in local DB


def get_cloud_sync_handler(config_path: Optional[Path] = None) -> Optional[CloudSyncHandler]:
    """
    Get a CloudSyncHandler from config.

    Returns None if cloud sync is not configured.
    """
    # TODO: Load config from .gryt/config
    # TODO: Check execution_mode
    # TODO: Create GrytCloudClient if credentials exist
    # For now, return None (no auto-sync)
    return None
