import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from shared.context.workflow_context import WorkflowContext
from schemas.agent_response import AgentResponse
from agents.agent8.agent import HRInterviewAgent
from services.agent8_api.dependencies import get_agent8

router = APIRouter()

@router.get("/health")
def get_health():
    """
    Health check endpoint. Returns operational status without triggering Agent 8.
    """
    return {
        "status": "healthy",
        "service": "agent8",
        "version": "v1"
    }

@router.post("/execute", response_model=AgentResponse)
def execute_agent(
    context: WorkflowContext,
    response: Response,
    x_correlation_id: Optional[str] = Header(None),
    x_idempotency_key: Optional[str] = Header(None),
    agent: HRInterviewAgent = Depends(get_agent8)
) -> AgentResponse:
    """
    Executes HR assessment & pool re-ranking workflow inside Agent 8.
    Accepts WorkflowContext, validates inputs, resolves dependencies,
    and returns AgentResponse.
    """
    correlation_id = x_correlation_id or str(uuid.uuid4())
    
    # Propagate headers back to client
    response.headers["X-Correlation-ID"] = correlation_id
    if x_idempotency_key:
        response.headers["X-Idempotency-Key"] = x_idempotency_key

    # Propagate details to context metadata for logging and execution metrics
    if not context.metadata:
        context.metadata = {}
    context.metadata["correlation_id"] = correlation_id
    if x_idempotency_key:
        context.metadata["idempotency_key"] = x_idempotency_key

    try:
        agent_response = agent.run(context)
        return agent_response
    except Exception as e:
        # Standard unhandled adapter exception -> HTTP 500
        raise HTTPException(
            status_code=500,
            detail=f"Unhandled internal service execution failure: {str(e)}"
        )
