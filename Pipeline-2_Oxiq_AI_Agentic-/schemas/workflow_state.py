from pydantic import BaseModel, Field
from typing import Optional

class WorkflowStateModel(BaseModel):
    """
    Pydantic schema representing the serialized execution state of a workflow runtime.
    Stored and updated by the StateManager.
    """
    workflow_id: str = Field(..., description="Unique UUID trace ID of the pipeline execution")
    candidate_id: str = Field(..., description="Target candidate UUID")
    current_state: str = Field(..., description="Current active state name")
    previous_state: Optional[str] = Field(None, description="Previous pipeline state name")
    retry_count: int = Field(0, description="Counter tracking transient error attempts")
    current_step: str = Field(..., description="Name of the active execution step")
    previous_step: Optional[str] = Field(None, description="Name of the last completed step")
    execution_time: float = Field(0.0, description="Total execution time accumulated across steps in seconds")
