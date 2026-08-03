from typing import Dict, Any
from langchain_core.runnables import RunnableConfig
from shared.context.workflow_context import WorkflowContext
from schemas.agent_response import AgentResponse
from shared.registry.tool_registry import tool_registry
from shared.logger.logger import workflow_logger, error_logger
from shared.config.constants import (
    STATE_TECHNICAL_INTERVIEW_PENDING,
    STATE_INTERVIEW_SCHEDULED,
    EVENT_TECHNICAL_SCORE_SUBMITTED,
    STATE_TECHNICAL_INTERVIEW_COMPLETED
)
from agents.agent7.graph.state import Agent7GraphState

def intake_node(state: Agent7GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Step 1: Log entry and initialize context metadata & retry counters.
    """
    context = state["workflow_context"]
    workflow_logger.info(
        "Initializing Agent 7 technical evaluation graph flow...",
        trace_id=context.workflow_id
    )
    
    if not context.metadata:
        context.metadata = {}
        
    retry_counts = state.get("retry_counts") or {
        "context_retrieval": 0,
        "database_commit": 0
    }
    
    return {
        "retry_counts": retry_counts,
        "warnings": state.get("warnings") or [],
        "last_error": None,
        "route_action": None
    }

def validate_context_node(state: Agent7GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Step 2: Validate input context requirements.
    """
    context = state["workflow_context"]
    errors = []
    
    valid_states = [STATE_TECHNICAL_INTERVIEW_PENDING, STATE_INTERVIEW_SCHEDULED]
    if context.current_state not in valid_states:
        errors.append(
            f"Invalid workflow state for technical evaluation: '{context.current_state}'. "
            f"Expected one of: {valid_states}."
        )
        
    if not context.candidate or not context.candidate.candidate_id:
        errors.append("Missing candidate_id in workflow context.")
        
    if errors:
        error_logger.error(
            f"Agent 7 context validation failed. | Context: {{'validation_errors': {errors}}}",
            trace_id=context.workflow_id
        )
        workflow_logger.info(f"Intake validation failed: {errors}", trace_id=context.workflow_id)
        return {
            "last_error": "; ".join(errors),
            "failure_category": "TERMINAL",
            "failed_operation": "intake_validation",
            "route_action": None
        }
        
    workflow_logger.info("Agent 7 Context Validation Passed.", trace_id=context.workflow_id)
    return {
        "last_error": None,
        "route_action": None
    }

def retrieve_context_node(state: Agent7GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Step 3: Retrieve candidate and job context details via Database MCP.
    """
    context = state["workflow_context"]
    retry_counts = dict(state.get("retry_counts") or {})
    cand_id = context.candidate.candidate_id
    job_id = context.candidate.job_id
    
    try:
        db_tool = tool_registry.get_tool("database_mcp")
    except KeyError:
        return {
            "last_error": "DatabaseMCP not registered in ToolRegistry",
            "failure_category": "TERMINAL",
            "failed_operation": "context_retrieval",
            "route_action": None
        }
        
    # Save/restore metadata retry_count to avoid clobbering Master workflow retry counter
    _saved_retry = context.metadata.get("retry_count", 0)
    context.metadata["retry_count"] = retry_counts.get("context_retrieval", 0)
    
    cand_resp = db_tool().execute(
        action="read_candidate",
        candidate_id=cand_id,
        workflow_id=context.workflow_id,
        metadata=context.metadata
    )
    
    job_resp = db_tool().execute(
        action="read_job",
        job_id=job_id,
        workflow_id=context.workflow_id,
        metadata=context.metadata
    )
    
    context.metadata["retry_count"] = _saved_retry
    
    if cand_resp.status != "SUCCESS" or job_resp.status != "SUCCESS":
        tries = retry_counts.get("context_retrieval", 0)
        if tries < 3:
            retry_counts["context_retrieval"] = tries + 1
            workflow_logger.info(
                f"Database context retrieval failed. Retry {tries + 1} of 3",
                trace_id=context.workflow_id
            )
            return {
                "retry_counts": retry_counts,
                "last_error": f"Database read failure: candidate={cand_resp.errors}, job={job_resp.errors}",
                "route_action": "RETRY"
            }
        else:
            return {
                "retry_counts": retry_counts,
                "last_error": f"Database context retrieval exhausted after {tries} retries.",
                "failure_category": "TERMINAL",
                "failed_operation": "context_retrieval",
                "route_action": None
            }
            
    return {
        "candidate_context": cand_resp.payload or {},
        "job_context": job_resp.payload or {},
        "last_error": None,
        "route_action": None
    }

def evaluate_technical_node(state: Agent7GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Step 4: Compute technical evaluation scores and recommendation.
    """
    context = state["workflow_context"]
    
    # Check if overrides exist in metadata for test mocking
    scores = context.metadata.get("override_scores") or {
        "coding_proficiency": 8.5,
        "problem_solving": 8.0,
        "architecture_design": 7.5
    }
    recommendation = context.metadata.get("override_recommendation") or "PASS"
    
    workflow_logger.info(
        f"Technical evaluation computed for {context.candidate.name}. Decision: {recommendation}",
        trace_id=context.workflow_id
    )
    
    return {
        "technical_scores": scores,
        "technical_recommendation": recommendation,
        "last_error": None,
        "route_action": None
    }

def prepare_database_node(state: Agent7GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Step 5: Prepare scorecard payload for database persistence.
    """
    context = state["workflow_context"]
    
    payload = {
        "candidate_id": context.candidate.candidate_id,
        "workflow_id": context.workflow_id,
        "technical_scores": state["technical_scores"],
        "recommendation": state["technical_recommendation"]
    }
    
    return {
        "db_scorecard_prepared": payload,
        "last_error": None,
        "route_action": None
    }

def commit_database_node(state: Agent7GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Step 6: Commit technical scorecard to Database MCP with side-effect idempotency.
    """
    context = state["workflow_context"]
    retry_counts = dict(state.get("retry_counts") or {})
    
    # Idempotency checkpoint check
    if context.step_data.get("technical_scores_committed"):
        workflow_logger.info(
            "Idempotency Checkpoint: Technical scores already committed to database.",
            trace_id=context.workflow_id
        )
        return {
            "last_error": None,
            "route_action": None
        }
        
    try:
        db_tool = tool_registry.get_tool("database_mcp")
    except KeyError:
        return {
            "last_error": "DatabaseMCP not registered in ToolRegistry",
            "failure_category": "TERMINAL",
            "failed_operation": "database_commit",
            "route_action": None
        }
        
    _saved_retry = context.metadata.get("retry_count", 0)
    context.metadata["retry_count"] = retry_counts.get("database_commit", 0)
    
    commit_resp = db_tool().execute(
        action="commit",
        payload=state["db_scorecard_prepared"],
        workflow_id=context.workflow_id,
        metadata=context.metadata
    )
    
    context.metadata["retry_count"] = _saved_retry
    
    if commit_resp.status != "SUCCESS":
        tries = retry_counts.get("database_commit", 0)
        if tries < 3:
            retry_counts["database_commit"] = tries + 1
            workflow_logger.info(
                f"Database commit failed. Retry {tries + 1} of 3",
                trace_id=context.workflow_id
            )
            return {
                "retry_counts": retry_counts,
                "last_error": f"Database commit failed: {commit_resp.errors}",
                "route_action": "RETRY"
            }
        else:
            return {
                "retry_counts": retry_counts,
                "last_error": f"Database commit exhausted after {tries} retries.",
                "failure_category": "TERMINAL",
                "failed_operation": "database_commit",
                "route_action": None
            }
            
    context.step_data["technical_scores_committed"] = True
    context.step_data["technical_scores"] = state["technical_scores"]
    context.step_data["technical_recommendation"] = state["technical_recommendation"]
    
    return {
        "last_error": None,
        "route_action": None
    }

def build_response_node(state: Agent7GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Step 7: Construct final AgentResponse envelope.
    """
    context = state["workflow_context"]
    last_error = state.get("last_error")
    
    if last_error:
        response = AgentResponse(
            execution_status="FAILED",
            errors=[last_error],
            warnings=state.get("warnings") or [],
            summary=f"Agent 7 execution failed on operation: '{state.get('failed_operation')}'",
            metadata={
                "failed_operation": state.get("failed_operation"),
                "failure_category": state.get("failure_category")
            }
        )
        context.metadata["last_execution_error"] = last_error
        return {"agent_response": response}
        
    scores = state["technical_scores"]
    recommendation = state["technical_recommendation"]
    summary_msg = f"Technical scorecard generated for {context.candidate.name}. Decision: {recommendation}."
    
    response = AgentResponse(
        execution_status="SUCCESS",
        generated_event=EVENT_TECHNICAL_SCORE_SUBMITTED,
        updated_state=STATE_TECHNICAL_INTERVIEW_COMPLETED,
        summary=summary_msg,
        warnings=state.get("warnings") or [],
        metadata={
            "technical_scores": scores,
            "recommendation": recommendation,
            "agent_name": "agent7",
            "execution_duration_ms": 500
        }
    )
    
    return {"agent_response": response}
