import time
from typing import Dict, Any, List
from langchain_core.runnables import RunnableConfig
from shared.context.workflow_context import WorkflowContext
from shared.logger.logger import workflow_logger
from schemas.agent_response import AgentResponse
from agents.agent6.models import InterviewMode, Interviewer, InterviewSlot, InterviewObject
from agents.agent6.validator import Validator
from agents.agent6.mode_selector import ModeSelector
from agents.agent6.interviewer_selector import InterviewerSelector
from agents.agent6.slot_selector import SlotSelector
from agents.agent6.builder import InterviewBuilder
from agents.agent6.response_builder import ResponseBuilder
from agents.agent6.tools import Agent6ToolsAdapter
from agents.agent6.compensation import CompensationManager
from agents.agent6.graph.state import Agent6GraphState

MAX_LOCAL_RETRIES = 3

def intake_node(state: Agent6GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Intakes the candidate data and sets up execution retry trackers.
    """
    context = state["workflow_context"]
    workflow_logger.info("Initializing Agent 6 scheduling graph flow...", trace_id=context.workflow_id)
    
    # Initialize operation retry counts
    retry_counts = {
        "calendar": 0,
        "meet": 0,
        "document": 0,
        "notification": 0,
        "database_read": 0
    }
    
    return {
        "retry_counts": retry_counts,
        "candidate_context": None,
        "job_context": None,
        "interviewer_score_breakdown": None,
        "slot_reason": None,
        "last_error": None,
        "failure_category": None,
        "failed_operation": None,
        "warnings": [],
        "route_action": None
    }

def validate_node(state: Agent6GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Validates candidate context payload schema locally.
    """
    context = state["workflow_context"]
    validator = Validator()
    is_valid, validation_errors = validator.validate(context)
    
    if not is_valid:
        workflow_logger.info(f"Intake validation failed: {validation_errors}", trace_id=context.workflow_id)
        return {
            "last_error": "; ".join(validation_errors),
            "failure_category": "TERMINAL",
            "failed_operation": "validate"
        }
    
    return {
        "last_error": None,
        "route_action": None
    }

def retrieve_resume_node(state: Agent6GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    MCP Action 1: Resume MCP call (Degraded Mode support).
    """
    context = state["workflow_context"]
    resume_url = context.candidate.resume_url
    
    resume_resp = Agent6ToolsAdapter.get_resume_summary(resume_url, context.workflow_id, context.metadata)
    
    if resume_resp.status != "SUCCESS":
        # Check if name and email are present to continue degraded
        if context.candidate.name and context.candidate.email:
            workflow_logger.info("Resume MCP call failed. Proceeding in degraded mode with available candidate context.", trace_id=context.workflow_id)
            context.metadata["degraded_mode"] = True
            context.metadata["degraded_reason"] = "Resume MCP unavailable"
            return {
                "warnings": state.get("warnings", []) + ["Resume MCP call failed. Operating degraded."],
                "last_error": None,
                "route_action": None
            }
        else:
            return {
                "last_error": f"Resume MCP call failed: {resume_resp.errors}",
                "failure_category": "TERMINAL",
                "failed_operation": "resume"
            }
            
    return {
        "last_error": None,
        "route_action": None
    }

def retrieve_database_context_node(state: Agent6GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    MCP Action 2: Database reads for candidate and job contexts.
    """
    context = state["workflow_context"]
    retry_counts = dict(state["retry_counts"])
    
    # 1. Read Candidate
    db_read_resp = Agent6ToolsAdapter.read_candidate(context.candidate.candidate_id, context.workflow_id, context.metadata)
    if db_read_resp.status != "SUCCESS":
        tries = retry_counts.get("database_read", 0)
        if tries < MAX_LOCAL_RETRIES:
            retry_counts["database_read"] = tries + 1
            workflow_logger.info(f"Database read failed. Retry {tries + 1} of {MAX_LOCAL_RETRIES}", trace_id=context.workflow_id)
            return {
                "retry_counts": retry_counts,
                "route_action": "RETRY",
                "last_error": None
            }
        else:
            return {
                "last_error": f"Database candidate read failed: {db_read_resp.errors}",
                "failure_category": "TERMINAL",
                "failed_operation": "database_read"
            }
            
    # 2. Read Job
    db_job_resp = Agent6ToolsAdapter.read_job(context.candidate.job_id, context.workflow_id, context.metadata)
    if db_job_resp.status != "SUCCESS":
        # Database reads are retryable
        tries = retry_counts.get("database_read", 0)
        if tries < MAX_LOCAL_RETRIES:
            retry_counts["database_read"] = tries + 1
            workflow_logger.info(f"Database job read failed. Retry {tries + 1} of {MAX_LOCAL_RETRIES}", trace_id=context.workflow_id)
            return {
                "retry_counts": retry_counts,
                "route_action": "RETRY",
                "last_error": None
            }
        else:
            return {
                "last_error": f"Database job read failed: {db_job_resp.errors}",
                "failure_category": "TERMINAL",
                "failed_operation": "database_read"
            }
            
    # 3. Validate Job payload
    job_payload = db_job_resp.payload
    validator = Validator()
    is_job_valid, job_errors = validator.validate_job_payload(job_payload, context.workflow_id)
    if not is_job_valid:
        return {
            "last_error": "; ".join(job_errors),
            "failure_category": "TERMINAL",
            "failed_operation": "database_read"
        }
        
    return {
        "candidate_context": db_read_resp.payload,
        "job_context": job_payload,
        "last_error": None,
        "route_action": None
    }

def select_mode_node(state: Agent6GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Step 2: Determine Interview Mode (Online vs Offline).
    """
    context = state["workflow_context"]
    mode = ModeSelector().select_mode(context)
    return {
        "interview_mode": mode,
        "last_error": None,
        "route_action": None
    }

def select_interviewer_node(state: Agent6GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Step 3: Select & Match Interviewer.
    """
    context = state["workflow_context"]
    job_payload = state.get("job_context")
    mode = state["interview_mode"]
    
    interviewer_id = context.step_data.get("interviewer_id")
    interviewer = None
    score_breakdown = {"total_score": 0, "reasons": []}
    
    if interviewer_id:
        selector = InterviewerSelector()
        interviewer = next((i for i in selector.mock_interviewers if i.interviewer_id == interviewer_id), None)
        score_breakdown = {"total_score": 100, "reasons": ["✓ Reused matching interviewer from checkpoint"]}
        workflow_logger.info(f"Idempotency: Reusing selected interviewer '{interviewer_id}'", trace_id=context.workflow_id)

    if not interviewer:
        try:
            interviewer_match = InterviewerSelector().select_interviewer(context, job_payload, mode)
            if not interviewer_match:
                return {
                    "last_error": "No eligible interviewer found matching candidate and job requirements.",
                    "failure_category": "TERMINAL",
                    "failed_operation": "interviewer_select"
                }
            interviewer, score_breakdown = interviewer_match
        except Exception as e:
            return {
                "last_error": str(e),
                "failure_category": "TERMINAL",
                "failed_operation": "interviewer_select"
            }
            
    return {
        "selected_interviewer": interviewer,
        "interviewer_score_breakdown": score_breakdown,
        "last_error": None,
        "route_action": None
    }

def select_slot_node(state: Agent6GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Step 4: Select Available Slot.
    """
    context = state["workflow_context"]
    interviewer = state["selected_interviewer"]
    
    scheduled_time = context.step_data.get("scheduled_time")
    slot = None
    slot_reason = "Reused matching slot from checkpoint"
    
    if scheduled_time:
        slot = InterviewSlot(slot_id=context.step_data.get("slot_id") or "slot-reused", label=scheduled_time)
        workflow_logger.info(f"Idempotency: Reusing scheduled slot '{scheduled_time}'", trace_id=context.workflow_id)
        
    if not slot:
        try:
            slot_match = SlotSelector().select_slot(context, interviewer.interviewer_id)
            if not slot_match:
                return {
                    "last_error": f"No available conflict-free slots found for interviewer '{interviewer.name}'.",
                    "failure_category": "TERMINAL",
                    "failed_operation": "slot_select"
                }
            slot, slot_reason = slot_match
        except Exception as e:
            return {
                "last_error": str(e),
                "failure_category": "TERMINAL",
                "failed_operation": "slot_select"
            }
            
    return {
        "selected_slot": slot,
        "slot_reason": slot_reason,
        "last_error": None,
        "route_action": None
    }

def reserve_calendar_node(state: Agent6GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    MCP Action 3: Calendar MCP reservation.
    """
    context = state["workflow_context"]
    interviewer = state["selected_interviewer"]
    slot = state["selected_slot"]
    retry_counts = dict(state["retry_counts"])
    
    booking_id = context.step_data.get("booking_id")
    if booking_id:
        workflow_logger.info(f"Idempotency Checkpoint: Skipped Calendar reservation. Reused booking '{booking_id}'", trace_id=context.workflow_id)
        return {
            "last_error": None,
            "route_action": None
        }
        
    cand_id = context.candidate.candidate_id
    calendar_key = f"pl2:{cand_id}:agent6:calendar_reservation"
    
    _saved_retry = context.metadata.get("retry_count", 0)
    context.metadata["retry_count"] = retry_counts.get("calendar", 0)
    cal_reserve_resp = Agent6ToolsAdapter.reserve_slot(
        slot.slot_id, interviewer.name, context.workflow_id,
        idempotency_key=calendar_key, metadata=context.metadata
    )
    context.metadata["retry_count"] = _saved_retry
    
    if cal_reserve_resp.status != "SUCCESS":
        # Check if slot unavailable (blacklist simulation hook)
        if "available" in str(cal_reserve_resp.errors).lower():
            workflow_logger.logger.warning(f"Slot {slot.label} unavailable. Blacklisting slot.")
            rejected = {
                "interviewer_id": interviewer.interviewer_id,
                "time_slot": slot.label
            }
            context.metadata.setdefault("rejected_recommendations", []).append(rejected)
            return {
                "last_error": f"Calendar reservation failed (unavailable): {cal_reserve_resp.errors}",
                "failure_category": "TERMINAL",
                "failed_operation": "calendar"
            }
            
        # Other failures are retryable locally
        tries = retry_counts.get("calendar", 0)
        if tries < MAX_LOCAL_RETRIES:
            retry_counts["calendar"] = tries + 1
            workflow_logger.info(f"Calendar reservation failed. Retry {tries + 1} of {MAX_LOCAL_RETRIES}", trace_id=context.workflow_id)
            return {
                "retry_counts": retry_counts,
                "route_action": "RETRY",
                "last_error": None
            }
        else:
            return {
                "last_error": f"Calendar reservation failed: {cal_reserve_resp.errors}",
                "failure_category": "TERMINAL",
                "failed_operation": "calendar",
                "route_action": None
            }
            
    booking_id = cal_reserve_resp.payload.get("booking_id")
    context.step_data["booking_id"] = booking_id
    context.step_data["calendar_reservation_idempotency_key"] = calendar_key
    
    return {
        "last_error": None,
        "route_action": None
    }

def create_meet_node(state: Agent6GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    MCP Action 4: Meet MCP generation.
    """
    context = state["workflow_context"]
    retry_counts = dict(state["retry_counts"])
    
    meeting_link = context.step_data.get("meeting_link")
    if meeting_link:
        workflow_logger.info(f"Idempotency Checkpoint: Skipped Meet generation. Reused meet link '{meeting_link}'", trace_id=context.workflow_id)
        return {
            "last_error": None,
            "route_action": None
        }
        
    cand_id = context.candidate.candidate_id
    meet_key = f"pl2:{cand_id}:agent6:meet_creation"
    
    _saved_retry = context.metadata.get("retry_count", 0)
    context.metadata["retry_count"] = retry_counts.get("meet", 0)
    meet_resp = Agent6ToolsAdapter.generate_meeting(
        context.workflow_id, idempotency_key=meet_key, metadata=context.metadata
    )
    context.metadata["retry_count"] = _saved_retry
    
    if meet_resp.status != "SUCCESS" or not meet_resp.payload or not meet_resp.payload.get("meeting_url"):
        tries = retry_counts.get("meet", 0)
        if tries < MAX_LOCAL_RETRIES:
            retry_counts["meet"] = tries + 1
            workflow_logger.info(f"Meet creation failed. Retry {tries + 1} of {MAX_LOCAL_RETRIES}", trace_id=context.workflow_id)
            return {
                "retry_counts": retry_counts,
                "route_action": "RETRY",
                "last_error": None
            }
        else:
            # Exhausted retries returns FALLBACK_ELIGIBLE for Master Fallback Engine
            return {
                "last_error": f"Meet link generation failed: {meet_resp.errors if meet_resp else 'Empty payload'}",
                "failure_category": "FALLBACK_ELIGIBLE",
                "failed_operation": "meet",
                "route_action": None
            }
            
    meeting_link = meet_resp.payload.get("meeting_url")
    context.step_data["meeting_link"] = meeting_link
    context.step_data["meet_creation_idempotency_key"] = meet_key
    
    return {
        "last_error": None,
        "route_action": None
    }

def build_interview_node(state: Agent6GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Builds the InterviewObject locally reusing InterviewBuilder.
    """
    context = state["workflow_context"]
    mode = state["interview_mode"]
    interviewer = state["selected_interviewer"]
    slot = state["selected_slot"]
    
    workflow_logger.info("Scheduling step: Build Interview Object", trace_id=context.workflow_id)
    builder = (
        InterviewBuilder()
        .with_context(context)
        .with_mode(mode)
        .with_interviewer(interviewer)
        .with_slot(slot)
        .with_status("SCHEDULED")
    )
        
    interview_obj = builder.build()
    return {
        "interview_object": interview_obj,
        "last_error": None,
        "route_action": None
    }

def generate_document_node(state: Agent6GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    MCP Action 5: Document MCP packet generation.
    """
    context = state["workflow_context"]
    interview_obj = state["interview_object"]
    retry_counts = dict(state.get("retry_counts") or {})
    
    packet_id = context.step_data.get("packet_id")
    if packet_id:
        workflow_logger.info(f"Idempotency Checkpoint: Skipped Document generation. Reused packet '{packet_id}'", trace_id=context.workflow_id)
        return {
            "last_error": None,
            "route_action": None
        }
        
    cand_id = context.candidate.candidate_id
    doc_key = f"pl2:{cand_id}:agent6:document_generation"
    
    _saved_retry = context.metadata.get("retry_count", 0)
    context.metadata["retry_count"] = retry_counts.get("document", 0)
    doc_resp = Agent6ToolsAdapter.generate_interview_packet(
        interview_obj.model_dump(), context.workflow_id,
        idempotency_key=doc_key, metadata=context.metadata
    )
    context.metadata["retry_count"] = _saved_retry
    
    if doc_resp.status != "SUCCESS":
        tries = retry_counts.get("document", 0)
        if tries < MAX_LOCAL_RETRIES:
            retry_counts["document"] = tries + 1
            workflow_logger.info(f"Document generation failed. Retry {tries + 1} of {MAX_LOCAL_RETRIES}", trace_id=context.workflow_id)
            return {
                "retry_counts": retry_counts,
                "route_action": "RETRY",
                "last_error": None
            }
        else:
            return {
                "last_error": f"Interview packet generation failed: {doc_resp.errors}",
                "failure_category": "RETRYABLE",
                "failed_operation": "document",
                "route_action": None
            }
            
    packet_id = doc_resp.payload.get("packet_id")
    context.step_data["packet_id"] = packet_id
    context.step_data["document_generation_idempotency_key"] = doc_key
    
    return {
        "last_error": None,
        "route_action": None
    }

def prepare_database_node(state: Agent6GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    MCP Action 6a: Prepare database state update payloads.
    """
    context = state["workflow_context"]
    interviewer = state["selected_interviewer"]
    slot = state["selected_slot"]
    
    update_prep = context.step_data.get("db_update_prepared")
    insert_prep = context.step_data.get("db_insert_prepared")
    
    cand_id = context.candidate.candidate_id
    db_write_key = f"pl2:{cand_id}:agent6:database_write"
    
    if not update_prep:
        update_prep_resp = Agent6ToolsAdapter.prepare_candidate_update(
            cand_id, "InterviewScheduled", context.workflow_id,
            idempotency_key=db_write_key, metadata=context.metadata
        )
        if update_prep_resp.status != "SUCCESS":
            return {
                "last_error": f"Database candidate update preparation failed: {update_prep_resp.errors}",
                "failure_category": "TERMINAL",
                "failed_operation": "database_prepare"
            }
        update_prep = update_prep_resp.payload
        context.step_data["db_update_prepared"] = update_prep
        context.step_data["database_write_idempotency_key"] = db_write_key
        
    if not insert_prep:
        insert_prep_resp = Agent6ToolsAdapter.prepare_database_payload(
            cand_id, interviewer.interviewer_id, slot.label, context.workflow_id,
            idempotency_key=db_write_key, metadata=context.metadata
        )
        if insert_prep_resp.status != "SUCCESS":
            return {
                "last_error": f"Database interview insertion preparation failed: {insert_prep_resp.errors}",
                "failure_category": "TERMINAL",
                "failed_operation": "database_prepare"
            }
        insert_prep = insert_prep_resp.payload
        context.step_data["db_insert_prepared"] = insert_prep
        
    return {
        "db_update_prepared": update_prep,
        "db_insert_prepared": insert_prep,
        "last_error": None,
        "route_action": None
    }

def commit_database_node(state: Agent6GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    MCP Action 6b: Commit database transaction. Executes side-effect compensation on failure.
    """
    context = state["workflow_context"]
    update_prep = state["db_update_prepared"] or context.step_data.get("db_update_prepared")
    insert_prep = state["db_insert_prepared"] or context.step_data.get("db_insert_prepared")
    
    db_committed = context.step_data.get("db_committed")
    if db_committed:
        workflow_logger.info("Idempotency Checkpoint: Database transaction already committed.", trace_id=context.workflow_id)
        return {
            "last_error": None,
            "route_action": None
        }
        
    commit_update_resp = Agent6ToolsAdapter.commit_transaction(update_prep, context.workflow_id, context.metadata)
    if commit_update_resp.status != "SUCCESS":
        CompensationManager.compensate(context, update_prep, insert_prep)
        return {
            "last_error": f"Database commit for candidate update failed: {commit_update_resp.errors}",
            "failure_category": "COMPENSATION_REQUIRED",
            "failed_operation": "database_commit"
        }
        
    commit_insert_resp = Agent6ToolsAdapter.commit_transaction(insert_prep, context.workflow_id, context.metadata)
    if commit_insert_resp.status != "SUCCESS":
        CompensationManager.compensate(context, update_prep, insert_prep)
        return {
            "last_error": f"Database commit for interview record failed: {commit_insert_resp.errors}",
            "failure_category": "COMPENSATION_REQUIRED",
            "failed_operation": "database_commit"
        }
        
    context.step_data["db_committed"] = True
    return {
        "last_error": None,
        "route_action": None
    }

def send_notification_node(state: Agent6GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    MCP Action 7: Notification dispatch (non-terminal).
    """
    context = state["workflow_context"]
    interviewer = state["selected_interviewer"]
    slot = state["selected_slot"]
    retry_counts = dict(state["retry_counts"])
    
    notification_sent = context.step_data.get("notification_sent")
    if notification_sent:
        workflow_logger.info("Idempotency Checkpoint: Notification already sent.", trace_id=context.workflow_id)
        return {
            "last_error": None,
            "route_action": None
        }
        
    cand_id = context.candidate.candidate_id
    notify_key = f"pl2:{cand_id}:agent6:notification"
    
    email_body = f"Hello {context.candidate.name}, you have been scheduled for an interview on {slot.label} with {interviewer.name}."
    _saved_retry = context.metadata.get("retry_count", 0)
    context.metadata["retry_count"] = retry_counts.get("notification", 0)
    notify_resp = Agent6ToolsAdapter.send_notification(
        context.candidate.email,
        "Interview Confirmation",
        email_body,
        context.workflow_id,
        idempotency_key=notify_key,
        metadata=context.metadata
    )
    context.metadata["retry_count"] = _saved_retry
    
    if notify_resp.status != "SUCCESS":
        tries = retry_counts.get("notification", 0)
        if tries < MAX_LOCAL_RETRIES:
            retry_counts["notification"] = tries + 1
            workflow_logger.info(f"Notification failed. Retry {tries + 1} of {MAX_LOCAL_RETRIES}", trace_id=context.workflow_id)
            return {
                "retry_counts": retry_counts,
                "route_action": "RETRY",
                "last_error": None
            }
        else:
            return {
                "last_error": f"Notification dispatch failed: {notify_resp.errors}",
                "failure_category": "RETRYABLE",
                "failed_operation": "notification",
                "route_action": None
            }
            
    context.step_data["notification_sent"] = True
    context.step_data["notification_idempotency_key"] = notify_key
    
    return {
        "last_error": None,
        "route_action": None
    }

def build_response_node(state: Agent6GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Constructs the final SUCCESS or FAILED AgentResponse envelope.
    """
    context = state["workflow_context"]
    last_error = state.get("last_error")
    
    if last_error:
        # Construct failure response
        builder = (
            ResponseBuilder()
            .with_status("FAILED")
            .with_errors([last_error])
            .with_warnings(state.get("warnings") or [])
            .with_summary(f"Agent 6 execution failed on operation: '{state.get('failed_operation')}'")
        )
        
        meta = {
            "failed_operation": state.get("failed_operation"),
            "failure_category": state.get("failure_category")
        }
        
        # If Meet generation exhausted retries, recommend Master fallback
        if state.get("failed_operation") == "meet" and state.get("failure_category") == "FALLBACK_ELIGIBLE":
            builder = builder.with_action("OFFLINE_FALLBACK")
            meta["suggested_action"] = "OFFLINE_FALLBACK"
            
        builder = builder.with_metadata(meta)
        context.metadata["last_execution_error"] = last_error
        
        return {"agent_response": builder.build()}
        
    # Construct success response
    interviewer = state["selected_interviewer"]
    slot = state["selected_slot"]
    interview_obj = state["interview_object"]
    score_breakdown = state.get("interviewer_score_breakdown") or {"total_score": 100, "reasons": []}
    slot_reason = state.get("slot_reason") or "Reused slot"
    
    # Save final details to step_data
    context.step_data["scheduled_time"] = slot.label
    context.step_data["slot_id"] = slot.slot_id
    context.step_data["interviewer_id"] = interviewer.interviewer_id
    context.step_data["interview_mode"] = state["interview_mode"].value
    
    summary_msg = (
        f"Interview successfully scheduled for {context.candidate.name} with "
        f"{interviewer.name} ({interviewer.role}) on {slot.label}."
    )
    
    response = (
        ResponseBuilder()
        .with_status("SUCCESS")
        .with_event_and_state("InterviewCreated", "InterviewScheduled")
        .with_warnings(state.get("warnings") or [])
        .with_summary(summary_msg)
        .with_metadata({
            **interview_obj.model_dump(),
            "interviewer_score": score_breakdown.get("total_score"),
            "interviewer_reasons": score_breakdown.get("reasons"),
            "slot_reason": slot_reason
        })
        .build()
    )
    
    workflow_logger.info("Agent 6 scheduling completed successfully.", trace_id=context.workflow_id)
    return {"agent_response": response}
