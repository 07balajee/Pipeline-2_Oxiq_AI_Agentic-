from fastapi import APIRouter, Depends, Header, HTTPException, status, Request
from typing import Optional, Dict
from agents.master.master_agent import MasterAgent
from services.master_api.dependencies import get_master_agent
from services.master_api.schemas import (
    WorkflowStartRequest, WorkflowStartResponse,
    WorkflowEventRequest, WorkflowEventResponse,
    WorkflowResumeRequest, WorkflowResumeResponse,
    WorkflowStatusResponse
)
from shared.events.base_event import BaseEvent
import uuid

router = APIRouter(prefix="/v1")

# Process-local idempotency map
_idempotency_map: Dict[str, str] = {}

def _get_correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", str(uuid.uuid4()))

@router.post("/workflow/start", status_code=201, response_model=WorkflowStartResponse)
def start_workflow(
    request: WorkflowStartRequest,
    x_idempotency_key: Optional[str] = Header(None),
    correlation_id: str = Depends(_get_correlation_id),
    master: MasterAgent = Depends(get_master_agent)
):
    # 1. Resolve idempotency key
    idem_key = x_idempotency_key or f"pipeline2:start:{request.candidate_data.candidate_id}:{request.job_data.job_id}"
    
    if idem_key in _idempotency_map:
        existing_wf_id = _idempotency_map[idem_key]
        try:
            status_data = master.get_workflow_status(existing_wf_id)
            return WorkflowStartResponse(
                workflow_id=existing_wf_id,
                status=status_data["graph_status"].lower()
            )
        except KeyError:
            # If context was cleared/not found, proceed to recreate
            pass

    # 2. Enrich metadata with correlation ID
    meta = request.metadata or {}
    meta["correlation_id"] = correlation_id
    
    # 3. Trigger start
    candidate_dict = request.candidate_data.model_dump()
    job_dict = request.job_data.model_dump()
    
    try:
        workflow_id = master.start_workflow(candidate_dict, job_dict, metadata=meta)
        _idempotency_map[idem_key] = workflow_id
        
        # Determine status
        status_data = master.get_workflow_status(workflow_id)
        return WorkflowStartResponse(
            workflow_id=workflow_id,
            status=status_data["graph_status"].lower()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start workflow: {str(e)}"
        )

@router.post("/workflow/event", response_model=WorkflowEventResponse)
def trigger_workflow_event(
    request: WorkflowEventRequest,
    correlation_id: str = Depends(_get_correlation_id),
    master: MasterAgent = Depends(get_master_agent)
):
    # Verify workflow exists
    if request.workflow_id not in master.active_contexts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow '{request.workflow_id}' not found."
        )
        
    context = master.active_contexts[request.workflow_id]
    context.metadata["correlation_id"] = correlation_id
    
    event = BaseEvent(
        name=request.event_name,
        candidate_id=context.candidate.candidate_id,
        payload=request.payload or {}
    )
    
    try:
        master.handle_event(event)
        return WorkflowEventResponse(
            workflow_id=request.workflow_id,
            new_state=context.current_state
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger event: {str(e)}"
        )

@router.post("/workflow/resume", response_model=WorkflowResumeResponse)
def resume_workflow(
    request: WorkflowResumeRequest,
    correlation_id: str = Depends(_get_correlation_id),
    master: MasterAgent = Depends(get_master_agent)
):
    # Verify workflow exists
    if request.workflow_id not in master.active_contexts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow '{request.workflow_id}' not found."
        )
        
    context = master.active_contexts[request.workflow_id]
    context.metadata["correlation_id"] = correlation_id
    
    # Verify workflow is actually paused
    status_data = master.get_workflow_status(request.workflow_id)
    if status_data["graph_status"] != "PAUSED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workflow '{request.workflow_id}' is not currently paused on approval."
        )
        
    try:
        payload = {"notes": request.notes} if request.notes else None
        resumed = master.resume_workflow(
            workflow_id=request.workflow_id,
            approval_type=request.approval_type,
            decision=request.action,
            payload=payload
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Resume failed: {str(e)}"
        )
        
    if resumed:
        return WorkflowResumeResponse(
            workflow_id=request.workflow_id,
            status="resumed"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workflow resume rejected or not applicable for type '{request.approval_type}'."
        )

@router.get("/workflow/{workflow_id}", response_model=WorkflowStatusResponse)
def get_workflow_status(
    workflow_id: str,
    master: MasterAgent = Depends(get_master_agent)
):
    try:
        status_data = master.get_workflow_status(workflow_id)
        return WorkflowStatusResponse(**status_data)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow '{workflow_id}' not found."
        )

@router.get("/health")
def health_check():
    return {"status": "healthy"}
