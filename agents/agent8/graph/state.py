from typing import TypedDict, Optional, Dict, Any, List
from shared.context.workflow_context import WorkflowContext
from schemas.agent_response import AgentResponse

class Agent8GraphState(TypedDict):
    """
    State definition for the Agent 8 (HR Assessment & Re-ranking) LangGraph orchestrator.
    Maintains minimal worker-local state; authoritative workflow state remains in WorkflowContext.
    """
    workflow_context: WorkflowContext
    
    candidate_context: Optional[Dict[str, Any]]
    job_context: Optional[Dict[str, Any]]
    
    hr_scores: Optional[Dict[str, float]]
    rank_index: Optional[int]
    recommendation: Optional[str]
    db_hr_payload_prepared: Optional[Dict[str, Any]]

    # Populated only when a real hr_evaluation payload is supplied (see
    # agents/agent8/scoring.py, confidence.py) - deterministic §8 formula
    # outputs, additive alongside the legacy placeholder fields above so
    # default-path behavior (no evaluation supplied) is unchanged.
    hr_score_composite: Optional[int]
    technical_score: Optional[float]
    final_score: Optional[str]
    confidence_score: Optional[float]
    anomalies: Optional[List[Dict[str, Any]]]
    
    # Bounded operational retry tracking
    retry_counts: Dict[str, int]
    
    # Error diagnostics
    last_error: Optional[str]
    failure_category: Optional[str]
    failed_operation: Optional[str]
    route_action: Optional[str]
    warnings: List[str]
    
    agent_response: Optional[AgentResponse]
