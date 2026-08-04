from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

class AgentResponse(BaseModel):
    """
    Structured output returned by all worker agents back to the Master Orchestrator.
    """
    execution_status: str = Field(..., description="'SUCCESS' or 'FAILED' execution flag")
    generated_event: Optional[str] = Field(None, description="Pipeline event triggered by this task completion")
    updated_state: Optional[str] = Field(None, description="Proposed next state flag for the state machine")
    summary: str = Field(..., description="Summary of work completed by the worker agent")
    errors: List[str] = Field(default_factory=list, description="List of error logs generated during worker execution")
    warnings: List[str] = Field(default_factory=list, description="List of warning messages")
    suggested_action: Optional[str] = Field(None, description="Suggested next action recommendation")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata metrics (duration, LLM tokens)")
