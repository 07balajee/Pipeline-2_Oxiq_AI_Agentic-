from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from shared.context.candidate_context import CandidateContext

class WorkflowContext(BaseModel):
    """
    Unified context container that encapsulates candidate profiles, execution history,
    active state flags, and step parameters. This is passed to worker agents.
    """
    workflow_id: str = Field(description="Unique correlation ID / trace ID for this execution run")
    candidate: CandidateContext
    current_state: str
    previous_state: Optional[str] = None
    
    # Store dynamic data collected during execution (schedule details, scorecards, etc.)
    step_data: Dict[str, Any] = Field(default_factory=dict)
    
    # List of transitions/events processed in this workflow
    history: List[str] = Field(default_factory=list)
    
    # Metadata for diagnostic details
    metadata: Dict[str, Any] = Field(default_factory=dict)
