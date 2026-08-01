from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid

class TraceStep(BaseModel):
    """
    Represents an isolated step or execution checkpoint in the workflow trace.
    Stores timestamps, execution speed, inputs/outputs, and actor details.
    """
    step_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    actor: str  # e.g., "MasterAgent", "Agent6", "GoogleCalendarMCP"
    action: str  # e.g., "RouteState", "BookCalendarSlot", "ParseScorecard"
    status: str  # "SUCCESS", "FAILED", "PAUSED"
    input_payload: Optional[Dict[str, Any]] = None
    output_payload: Optional[Dict[str, Any]] = None
    duration_ms: float = 0.0

class WorkflowTrace(BaseModel):
    """
    Unified telemetry log tracking candidate progression.
    Compiles chronological execution traces for debugging and auditing.
    """
    trace_id: str
    candidate_id: str
    start_time: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    end_time: Optional[str] = None
    steps: List[TraceStep] = Field(default_factory=list)
    final_status: str = "IN_PROGRESS"

    def add_step(
        self,
        actor: str,
        action: str,
        status: str,
        duration_ms: float,
        input_payload: Optional[Dict[str, Any]] = None,
        output_payload: Optional[Dict[str, Any]] = None
    ):
        """
        Appends an execution step to the telemetry trace.
        """
        step = TraceStep(
            actor=actor,
            action=action,
            status=status,
            duration_ms=duration_ms,
            input_payload=input_payload,
            output_payload=output_payload
        )
        self.steps.append(step)
