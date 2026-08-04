from typing import TypedDict, Optional, Dict, Any
from shared.context.workflow_context import WorkflowContext
from schemas.agent_response import AgentResponse

class MasterGraphState(TypedDict):
    """
    State definition for the Master Agent LangGraph.
    Encapsulates event trigger details, resolved routing endpoints,
    execution response details, and graph lifecycle status.
    All primary candidate contexts remain inside the workflow_context object.
    """
    workflow_context: WorkflowContext
    incoming_event: str
    event_payload: Optional[Dict[str, Any]]
    
    # Target resolution details populated by route_node
    target_agent: Optional[str]
    next_state: Optional[str]
    
    # Transport outputs from dispatch_node
    agent_response: Optional[AgentResponse]
    transport_error: Optional[str]
    
    # Graph execution status
    graph_status: str  # "RUNNING", "PAUSED", "EVENT_COMPLETED", "WORKFLOW_COMPLETED", "FAILED"
