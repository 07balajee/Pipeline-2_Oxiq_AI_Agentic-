from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from schemas.candidate import CandidateModel
from schemas.job import JobModel

class WorkflowStartRequest(BaseModel):
    candidate_data: CandidateModel
    job_data: JobModel
    metadata: Optional[Dict[str, Any]] = None

class WorkflowStartResponse(BaseModel):
    workflow_id: str
    status: str

class WorkflowEventRequest(BaseModel):
    workflow_id: str
    event_name: str
    payload: Optional[Dict[str, Any]] = None

class WorkflowEventResponse(BaseModel):
    workflow_id: str
    new_state: str

class WorkflowResumeRequest(BaseModel):
    workflow_id: str
    approval_type: str
    action: str = Field(..., description="Decision action: APPROVE or REJECT")
    notes: Optional[str] = None

class WorkflowResumeResponse(BaseModel):
    workflow_id: str
    status: str

class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    current_state: str
    graph_status: str
    approval_status: Optional[str] = None
    approval_type: Optional[str] = None
    last_event: Optional[str] = None
    last_agent: Optional[str] = None
    timeline: List[Dict[str, Any]] = Field(default_factory=list)
    step_data: Dict[str, Any] = Field(default_factory=dict)
    failure: Optional[str] = None

class DependencyHealth(BaseModel):
    status: str
    url: str
    latency_ms: Optional[float] = None
    error: Optional[str] = None

class ReadinessResponse(BaseModel):
    status: str
    dependencies: Dict[str, DependencyHealth]
