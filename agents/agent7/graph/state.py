from typing import TypedDict, Optional, Dict, Any, List
from shared.context.workflow_context import WorkflowContext
from schemas.agent_response import AgentResponse

class Agent7GraphState(TypedDict):
    """
    State definition for the Agent 7 (Technical Evaluation) LangGraph orchestrator.
    Maintains minimal worker-local state; authoritative workflow state remains in WorkflowContext.
    """
    workflow_context: WorkflowContext
    
    candidate_context: Optional[Dict[str, Any]]
    job_context: Optional[Dict[str, Any]]
    
    technical_scores: Optional[Dict[str, float]]
    technical_recommendation: Optional[str]
    db_scorecard_prepared: Optional[Dict[str, Any]]
    
    # Bounded operational retry tracking
    retry_counts: Dict[str, int]
    
    # Error diagnostics
    last_error: Optional[str]
    failure_category: Optional[str]
    failed_operation: Optional[str]
    route_action: Optional[str]
    warnings: List[str]
    
    agent_response: Optional[AgentResponse]
