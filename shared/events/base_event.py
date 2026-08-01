from pydantic import BaseModel, Field
from datetime import datetime
import uuid
from typing import Any, Dict

class BaseEvent(BaseModel):
    """
    Standard event structure produced and consumed throughout the orchestration pipeline.
    """
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str  # Name of the event type (e.g. CandidateShortlisted)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    candidate_id: str
    payload: Dict[str, Any] = Field(default_factory=dict)
