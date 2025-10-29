"""
EventBus for lifecycle events (v0.2.0)

Provides pub/sub mechanism for generation/evolution lifecycle events.
Used to trigger cloud sync, hooks, notifications, etc.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List
from collections import defaultdict
import logging


logger = logging.getLogger(__name__)


class Event:
    """An event with a name and payload"""

    def __init__(self, name: str, payload: Dict[str, Any]):
        self.name = name
        self.payload = payload

    def __repr__(self) -> str:
        return f"Event(name={self.name}, payload={self.payload})"


EventHandler = Callable[[Event], None]


class EventBus:
    """
    Simple pub/sub event bus for lifecycle events.

    Events:
        - generation.created: When a generation is created
        - generation.updated: When a generation is updated
        - generation.promoted: When a generation is promoted
        - evolution.created: When an evolution is created
        - evolution.completed: When an evolution finishes
        - evolution.failed: When an evolution fails
    """

    def __init__(self):
        self._handlers: Dict[str, List[EventHandler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        """Subscribe a handler to an event"""
        self._handlers[event_name].append(handler)
        logger.debug(f"Subscribed handler to {event_name}")

    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        """Unsubscribe a handler from an event"""
        if event_name in self._handlers:
            self._handlers[event_name].remove(handler)
            logger.debug(f"Unsubscribed handler from {event_name}")

    def emit(self, event_name: str, payload: Dict[str, Any]) -> None:
        """Emit an event to all subscribed handlers"""
        event = Event(event_name, payload)
        logger.debug(f"Emitting event: {event_name}")

        handlers = self._handlers.get(event_name, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in event handler for {event_name}: {e}")

    def clear(self) -> None:
        """Clear all subscriptions (useful for testing)"""
        self._handlers.clear()


# Global event bus instance
_global_bus = EventBus()


def get_event_bus() -> EventBus:
    """Get the global event bus instance"""
    return _global_bus
