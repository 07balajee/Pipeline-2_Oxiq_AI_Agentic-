from typing import TypedDict, Optional, Dict, Any, List
from shared.context.workflow_context import WorkflowContext
from schemas.agent_response import AgentResponse
from agents.agent6.models import InterviewMode, Interviewer, InterviewSlot, InterviewObject

class Agent6GraphState(TypedDict):
    """
    State definition for the Agent 6 LangGraph orchestrator.
    Keeps a minimal footprint; authoritative checkpoint variables reside inside context.step_data.
    """
    workflow_context: WorkflowContext
    
    interview_mode: Optional[InterviewMode]
    selected_interviewer: Optional[Interviewer]
    selected_slot: Optional[InterviewSlot]
    interview_object: Optional[InterviewObject]
    
    db_update_prepared: Optional[Dict[str, Any]]
    db_insert_prepared: Optional[Dict[str, Any]]
    
    # Context retrieved from Database MCP
    candidate_context: Optional[Dict[str, Any]]
    job_context: Optional[Dict[str, Any]]
    
    # Metadata for matches
    interviewer_score_breakdown: Optional[Dict[str, Any]]
    slot_reason: Optional[str]
    
    # Bounded operations retry counters
    retry_counts: Dict[str, int]
    
    # Failure diagnostics
    last_error: Optional[str]
    failure_category: Optional[str]
    failed_operation: Optional[str]
    route_action: Optional[str]
    warnings: List[str]
    
    agent_response: Optional[AgentResponse]
