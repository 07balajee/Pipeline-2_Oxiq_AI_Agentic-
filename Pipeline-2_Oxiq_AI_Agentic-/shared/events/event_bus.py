from typing import Callable, Dict, List
from shared.events.base_event import BaseEvent
from shared.logger.logger import workflow_logger

class EventBus:
    """
    An in-memory publisher-subscriber event bus.
    Routes system events dynamically to registered callbacks.
    """
    def __init__(self):
        self._listeners: Dict[str, List[Callable[[BaseEvent], None]]] = {}

    def subscribe(self, event_name: str, callback: Callable[[BaseEvent], None]):
        """
        Registers a callback listener for a specific event name.
        """
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(callback)
        workflow_logger.info(f"Subscribed callback to event: {event_name}")

    def publish(self, event: BaseEvent):
        """
        Publishes an event to all registered listeners.
        """
        event_name = event.name
        workflow_logger.info(f"Publishing event: {event_name}", trace_id=event.candidate_id)
        
        if event_name in self._listeners:
            for callback in self._listeners[event_name]:
                try:
                    callback(event)
                except Exception as e:
                    workflow_logger.logger.error(
                        f"Error executing callback for event {event_name}: {str(e)}"
                    )

# Global event bus instance
event_bus = EventBus()
