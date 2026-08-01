from datetime import datetime
from typing import Dict, List, Any
from shared.events.base_event import BaseEvent

class EventStore:
    """
    Manages active, completed, and failed events, tracking lifecycle stages.
    Provides foundational support for potential replay logs.
    """
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    def log_event(self, event: BaseEvent, lifecycle_state: str):
        """
        Logs a state update for the given event's lifecycle.
        States: Created, Queued, Executing, Completed, Failed, Archived.
        """
        # Resolve unique event ID or compile a timestamp proxy
        event_id = getattr(event, "event_id", None) or f"evt-{int(datetime.now().timestamp() * 1000)}"
        
        if event_id not in self._store:
            self._store[event_id] = {
                "event_name": event.name,
                "candidate_id": event.candidate_id,
                "history": []
            }
            
        self._store[event_id]["history"].append({
            "state": lifecycle_state,
            "timestamp": datetime.now().isoformat()
        })

    def get_event_history(self, event_id: str) -> List[Dict[str, Any]]:
        """
        Returns lifecycle history entries for a given event ID.
        """
        return self._store.get(event_id, {}).get("history", [])
