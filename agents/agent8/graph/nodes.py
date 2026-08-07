from typing import Dict, Any
from langchain_core.runnables import RunnableConfig
from shared.context.workflow_context import WorkflowContext
from schemas.agent_response import AgentResponse
from shared.logger.logger import workflow_logger, error_logger
from shared.config.constants import (
    STATE_HR_INTERVIEW_PENDING,
    STATE_TECHNICAL_INTERVIEW_COMPLETED,
    EVENT_HR_SCORE_SUBMITTED,
    STATE_HR_INTERVIEW_COMPLETED
)
from agents.agent8.graph.state import Agent8GraphState
from agents.agent8 import scoring, confidence
from agents.agent8.tools import Agent8ToolsAdapter

def intake_node(state: Agent8GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Step 1: Log entry and initialize context metadata & retry counters.
    """
    context = state["workflow_context"]
    workflow_logger.info(
        "Initializing Agent 8 HR evaluation & pool re-ranking graph flow...",
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

def validate_context_node(state: Agent8GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Step 2: Validate input context requirements.
    """
    context = state["workflow_context"]
    errors = []
    
    valid_states = [STATE_HR_INTERVIEW_PENDING, STATE_TECHNICAL_INTERVIEW_COMPLETED]
    if context.current_state not in valid_states:
        errors.append(
            f"Invalid workflow state for HR evaluation: '{context.current_state}'. "
            f"Expected one of: {valid_states}."
        )
        
    if not context.candidate or not context.candidate.candidate_id:
        errors.append("Missing candidate_id in workflow context.")
        
    if errors:
        error_logger.error(
            f"Agent 8 context validation failed. | Context: {{'validation_errors': {errors}}}",
            trace_id=context.workflow_id
        )
        workflow_logger.info(f"Intake validation failed: {errors}", trace_id=context.workflow_id)
        return {
            "last_error": "; ".join(errors),
            "failure_category": "TERMINAL",
            "failed_operation": "intake_validation",
            "route_action": None
        }
        
    workflow_logger.info("Agent 8 Context Validation Passed.", trace_id=context.workflow_id)
    return {
        "last_error": None,
        "route_action": None
    }

def retrieve_context_node(state: Agent8GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Step 3: Retrieve candidate and job context details via Database MCP.
    """
    context = state["workflow_context"]
    retry_counts = dict(state.get("retry_counts") or {})
    cand_id = context.candidate.candidate_id
    job_id = context.candidate.job_id

    # Save/restore metadata retry_count to avoid clobbering Master workflow retry counter
    _saved_retry = context.metadata.get("retry_count", 0)
    context.metadata["retry_count"] = retry_counts.get("context_retrieval", 0)

    cand_resp = Agent8ToolsAdapter.read_candidate(cand_id, context.workflow_id, context.metadata)
    job_resp = Agent8ToolsAdapter.read_job(job_id, context.workflow_id, context.metadata)

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

def evaluate_hr_node(state: Agent8GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Step 4: Compute HR soft-skills evaluation scores.

    When the caller supplies context.metadata["hr_evaluation"] (real
    interviewer ratings: communication_rating, culture_fit_rating,
    behaviour_rating, and motivation_rating or leadership_rating - each
    1-5), the HR composite is computed deterministically via
    agents/agent8/scoring.py (Decimal + ROUND_HALF_UP, spec §8.1) instead of
    being fabricated. With no evaluation supplied, behavior is unchanged from
    the original placeholder values, so existing callers keep working.
    """
    context = state["workflow_context"]

    override_scores = context.metadata.get("override_hr_scores")
    evaluation = context.metadata.get("hr_evaluation")
    hr_score_composite = None

    if override_scores:
        scores = override_scores
    elif evaluation:
        is_leadership_track = str(context.metadata.get("job_grade", "L3")).lower().startswith("lead")
        try:
            hr_score_composite = scoring.compute_hr_score(
                evaluation["communication_rating"], evaluation["culture_fit_rating"],
                evaluation["behaviour_rating"], evaluation.get("motivation_rating"),
                evaluation.get("leadership_rating"), is_leadership_track,
            )
        except (KeyError, ValueError) as e:
            error_logger.error(f"Agent 8 hr_evaluation payload invalid: {e}", trace_id=context.workflow_id)
            return {
                "last_error": f"Invalid hr_evaluation payload: {e}",
                "failure_category": "TERMINAL",
                "failed_operation": "hr_evaluation",
                "route_action": None
            }
        # Legacy 0-10 display sub-scores, derived from the same ratings.
        scores = {
            "culture_fit": evaluation["culture_fit_rating"] * 2,
            "communication": evaluation["communication_rating"] * 2,
            "leadership_potential": (evaluation.get("leadership_rating") or evaluation.get("motivation_rating") or 4) * 2,
        }
    else:
        scores = {
            "culture_fit": 9.0,
            "communication": 8.5,
            "leadership_potential": 8.0
        }

    recommendation = context.metadata.get("override_recommendation") or "PASS"

    workflow_logger.info(
        f"HR evaluation computed for {context.candidate.name}. Decision: {recommendation}",
        trace_id=context.workflow_id
    )

    return {
        "hr_scores": scores,
        "hr_score_composite": hr_score_composite,
        "recommendation": recommendation,
        "last_error": None,
        "route_action": None
    }

def calculate_ranking_node(state: Agent8GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Step 5: Compute candidate cohort re-ranking.

    When Step 4 produced a real hr_score_composite (see evaluate_hr_node),
    this also computes a real consolidated final_score and confidence via
    agents/agent8/scoring.py + confidence.py (spec §8.2-8.4). True
    multi-candidate cohort ranking needs a shared cohort store this graph
    doesn't have yet, so the candidate is ranked against a cohort of one
    (rank 1 by construction) - the formula and anomaly/confidence detection
    are real, the cohort comparison is not. Falls back to the original
    placeholder (rank 1, no scoring) when no real hr_score_composite is
    available, matching prior behavior exactly.
    """
    context = state["workflow_context"]
    hr_score_composite = state.get("hr_score_composite")

    technical_score = None
    final_score = None
    confidence_score = None
    anomalies = None
    recommendation_override = None

    if context.metadata.get("override_rank_index"):
        rank = context.metadata["override_rank_index"]
    elif hr_score_composite is not None:
        technical_scores = context.step_data.get("technical_scores")
        if technical_scores:
            values = [v for v in technical_scores.values() if isinstance(v, (int, float))]
            technical_score = round(sum(values) / len(values) * 10, 1) if values else 75.0
        else:
            technical_score = 75.0

        weights = context.metadata.get("hr_weights", {"technical": 0.60, "hr": 0.40})
        positions_available = context.metadata.get("positions_available", 1)

        final = scoring.compute_final_score(technical_score, hr_score_composite, weights)
        candidate_score = scoring.CandidateScore(
            candidate_id=1, technical_score=technical_score,
            hr_score=hr_score_composite, final_score=final,
        )
        ranked, ties = scoring.rank_cohort([candidate_score])
        candidate_score.recommendation = scoring.recommend(
            candidate_score.rank, final, positions_available, technical_score, hr_score_composite
        )
        anomalies = scoring.detect_anomalies(ranked, positions_available)
        confidence_score = confidence.compute_confidence(anomalies, ties)

        rank = candidate_score.rank
        final_score = str(final)
        # Map spec §8.4 vocabulary (Selected/Waitlist/Rejected) onto this
        # service's existing PASS/FAIL recommendation field.
        recommendation_override = "PASS" if candidate_score.recommendation in ("Selected", "Waitlist") else "FAIL"
    else:
        rank = 1

    workflow_logger.info(
        f"Candidate {context.candidate.name} cohort re-ranking computed: #{rank}",
        trace_id=context.workflow_id
    )

    result: Dict[str, Any] = {
        "rank_index": rank,
        "technical_score": technical_score,
        "final_score": final_score,
        "confidence_score": confidence_score,
        "anomalies": anomalies,
        "last_error": None,
        "route_action": None
    }
    if recommendation_override:
        result["recommendation"] = recommendation_override
    return result

def prepare_database_node(state: Agent8GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Step 6: Prepare combined HR evaluation and ranking payload for DB persistence.
    """
    context = state["workflow_context"]
    
    payload = {
        "candidate_id": context.candidate.candidate_id,
        "workflow_id": context.workflow_id,
        "hr_scores": state["hr_scores"],
        "rank_index": state["rank_index"],
        "recommendation": state["recommendation"]
    }
    if state.get("hr_score_composite") is not None:
        payload["hr_score_composite"] = state["hr_score_composite"]
    if state.get("final_score") is not None:
        payload["final_score"] = state["final_score"]

    return {
        "db_hr_payload_prepared": payload,
        "last_error": None,
        "route_action": None
    }

def commit_database_node(state: Agent8GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Step 7: Commit HR scorecard & ranking to Database MCP with side-effect idempotency.
    """
    context = state["workflow_context"]
    retry_counts = dict(state.get("retry_counts") or {})
    
    # Idempotency checkpoint check
    if context.step_data.get("hr_scores_committed"):
        workflow_logger.info(
            "Idempotency Checkpoint: HR scores and ranking already committed to database.",
            trace_id=context.workflow_id
        )
        return {
            "last_error": None,
            "route_action": None
        }
        
    _saved_retry = context.metadata.get("retry_count", 0)
    context.metadata["retry_count"] = retry_counts.get("database_commit", 0)

    commit_resp = Agent8ToolsAdapter.commit_hr_results(
        state["db_hr_payload_prepared"], context.workflow_id, context.metadata
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
            
    context.step_data["hr_scores_committed"] = True
    context.step_data["hr_scores"] = state["hr_scores"]
    context.step_data["cohort_rank"] = state["rank_index"]
    context.step_data["final_recommendation"] = state["recommendation"]
    
    return {
        "last_error": None,
        "route_action": None
    }

def build_response_node(state: Agent8GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Step 8: Construct final AgentResponse envelope.
    """
    context = state["workflow_context"]
    last_error = state.get("last_error")
    
    if last_error:
        response = AgentResponse(
            execution_status="FAILED",
            errors=[last_error],
            warnings=state.get("warnings") or [],
            summary=f"Agent 8 execution failed on operation: '{state.get('failed_operation')}'",
            metadata={
                "failed_operation": state.get("failed_operation"),
                "failure_category": state.get("failure_category")
            }
        )
        context.metadata["last_execution_error"] = last_error
        return {"agent_response": response}
        
    scores = state["hr_scores"]
    rank = state["rank_index"]
    recommendation = state["recommendation"]
    summary_msg = f"HR assessment completed. Candidate {context.candidate.name} ranked #{rank} in cohort."

    metadata = {
        "hr_scores": scores,
        "rank_index": rank,
        "recommendation": recommendation,
        "agent_name": "agent8",
        "execution_duration_ms": 500
    }
    # Real deterministic §8 outputs, present only when a real hr_evaluation
    # payload was supplied (see evaluate_hr_node/calculate_ranking_node).
    if state.get("hr_score_composite") is not None:
        metadata["hr_score_composite"] = state["hr_score_composite"]
    if state.get("technical_score") is not None:
        metadata["technical_score"] = state["technical_score"]
    if state.get("final_score") is not None:
        metadata["final_score"] = state["final_score"]
    if state.get("confidence_score") is not None:
        metadata["confidence_score"] = state["confidence_score"]
    if state.get("anomalies"):
        metadata["anomalies"] = state["anomalies"]

    response = AgentResponse(
        execution_status="SUCCESS",
        generated_event=EVENT_HR_SCORE_SUBMITTED,
        updated_state=STATE_HR_INTERVIEW_COMPLETED,
        summary=summary_msg,
        warnings=state.get("warnings") or [],
        metadata=metadata
    )

    return {"agent_response": response}
