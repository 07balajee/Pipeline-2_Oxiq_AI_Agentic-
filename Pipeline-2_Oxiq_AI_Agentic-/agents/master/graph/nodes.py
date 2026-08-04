import time
from typing import Dict, Any, Optional
from langchain_core.runnables import RunnableConfig
from shared.events.base_event import BaseEvent
from shared.config.constants import (
    STATE_OFFER_PIPELINE_TRIGGERED,
    STATE_CANDIDATE_REJECTED,
    STATE_WORKFLOW_PAUSED
)
from shared.clients.agent_client import AgentTransportError
from agents.master.graph.state import MasterGraphState

def intake_node(state: MasterGraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Validates incoming payload context and prepares tracing logs.
    """
    context = state["workflow_context"]
    event_name = state["incoming_event"]
    event_payload = state["event_payload"] or {}
    
    context_manager = config["configurable"]["context_manager"]
    event_store = config["configurable"]["event_store"]
    timeline = config["configurable"]["timeline"]
    
    # 1. Log event entry lifecycle stage
    event = BaseEvent(
        name=event_name,
        candidate_id=context.candidate.candidate_id,
        payload=event_payload
    )
    if "event_id" in event_payload:
        event.event_id = event_payload["event_id"]
        
    event_store.log_event(event, "Queued")
    event_store.log_event(event, "Executing")
    timeline.add_milestone(f"Event Received: {event_name}")
    
    # 2. Enrich context variables
    context_manager.prepare_execution_context(context, event)
    context.metadata["last_event_processed"] = event_name
    
    return {
        "workflow_context": context,
        "graph_status": "RUNNING",
        "agent_response": None,
        "transport_error": None
    }

def route_node(state: MasterGraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Invokes the Router/WorkflowEngine to determine the target worker and state.
    """
    context = state["workflow_context"]
    event_name = state["incoming_event"]
    
    workflow_engine = config["configurable"]["workflow_engine"]
    trace = config["configurable"]["trace"]
    
    start_time = time.time()
    next_state, target_agent = workflow_engine.resolve_next_step(context, event_name)
    duration_ms = (time.time() - start_time) * 1000
    
    # Log route step
    trace.add_step(
        actor="MasterAgent",
        action=f"RouteStateFrom_{context.current_state}_Via_{event_name}",
        status="SUCCESS",
        duration_ms=duration_ms,
        input_payload={"event": event_name, "current_state": context.current_state},
        output_payload={"next_state": next_state, "target_agent": target_agent}
    )
    
    return {
        "target_agent": target_agent,
        "next_state": next_state
    }

def dispatch_node(state: MasterGraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Executes worker invocation via the dynamic Dispatcher interface.
    """
    context = state["workflow_context"]
    target_agent = state["target_agent"]
    
    if not target_agent:
        return {}
        
    dispatcher = config["configurable"]["dispatcher"]
    state_manager = config["configurable"]["state_manager"]
    timeline = config["configurable"]["timeline"]
    
    context.metadata["last_agent_dispatched"] = target_agent
    timeline.add_milestone(f"Invoking Worker Agent: {target_agent}")
    agent_start = time.time()
    
    try:
        response = dispatcher.dispatch(target_agent, context)
        agent_duration = (time.time() - agent_start) * 1000
        state_manager.accumulate_time(context.workflow_id, agent_duration / 1000.0)
        
        return {
            "agent_response": response,
            "transport_error": None
        }
    except Exception as e:
        agent_duration = (time.time() - agent_start) * 1000
        error_msg = str(e)
        
        # Distinguish transport category errors vs generic runtime crashes
        category = "CONNECTION_ERROR"
        if isinstance(e, AgentTransportError):
            category = e.category
            
        context.metadata["last_execution_error"] = error_msg
        
        return {
            "agent_response": None,
            "transport_error": f"[{category}] {error_msg}"
        }

def response_validation_node(state: MasterGraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Validates output responses returned by worker agents.
    """
    context = state["workflow_context"]
    target_agent = state["target_agent"]
    response = state["agent_response"]
    
    response_validator = config["configurable"]["response_validator"]
    retry_engine = config["configurable"]["retry_engine"]
    timeline = config["configurable"]["timeline"]
    trace = config["configurable"]["trace"]
    
    is_valid, validation_errors = response_validator.validate_response(target_agent, response)
    
    if not is_valid:
        error_msg = ", ".join(validation_errors)
        if response and response.errors:
            error_msg += f" (Agent errors: {', '.join(response.errors)})"
            context.metadata["last_execution_error"] = ", ".join(response.errors)
        return {
            "workflow_context": context,
            "agent_response": None,
            "transport_error": f"[CONTRACT_ERROR] {error_msg}"
        }
        
    # Validation succeeded — reset retry counter and log metrics
    retry_engine.reset_retry_count(context)
    timeline.add_milestone(f"Agent {target_agent} completed successfully")
    
    # Update metrics trace step
    step_duration = 10.0
    trace.add_step(
        actor=target_agent,
        action="RunTask",
        status=response.execution_status,
        duration_ms=step_duration,
        input_payload={"context_state": context.previous_state},
        output_payload=response.model_dump()
    )
    
    return {
        "workflow_context": context,
        "graph_status": "EVENT_COMPLETED"
    }

def state_transition_node(state: MasterGraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Persists successful state updates to database and timeline trackers.
    """
    context = state["workflow_context"]
    next_state = state["next_state"]
    incoming_event = state["incoming_event"]
    
    state_manager = config["configurable"]["state_manager"]
    timeline = config["configurable"]["timeline"]
    trace = config["configurable"]["trace"]
    
    # 1. Update states
    context.previous_state = context.current_state
    context.current_state = next_state
    state_manager.update_state(context.workflow_id, next_state, current_step=f"Process_{incoming_event}")
    
    timeline.add_milestone(f"State transitioned: {context.previous_state} -> {next_state}")
    
    # Determine finality status
    if next_state == STATE_OFFER_PIPELINE_TRIGGERED:
        status = "WORKFLOW_COMPLETED"
    elif next_state == STATE_CANDIDATE_REJECTED:
        trace.final_status = "REJECTED"
        timeline.add_milestone("Workflow ended: Candidate Rejected")
        status = "WORKFLOW_COMPLETED"
    else:
        # If there is a target agent to run, keep state running; otherwise it is a wait state
        status = "RUNNING" if state["target_agent"] else "EVENT_COMPLETED"
        
    return {
        "workflow_context": context,
        "graph_status": status
    }

def retry_node(state: MasterGraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Handles Master-level worker re-invocation rules.
    """
    context = state["workflow_context"]
    agent_name = state["target_agent"]
    
    retry_engine = config["configurable"]["retry_engine"]
    timeline = config["configurable"]["timeline"]
    
    if retry_engine.should_retry(context):
        attempt = retry_engine.increment_retry_count(context)
        timeline.add_milestone(f"Retry attempt {attempt} for agent {agent_name}")
        
        return {
            "incoming_event": "RetryRequested",
            "event_payload": {"failed_agent": agent_name, "attempt": attempt},
            "graph_status": "RUNNING"
        }
        
    return {
        "incoming_event": "RetriesExhausted",
        "graph_status": "RUNNING"  # Transitions to fallback evaluation next
    }

def fallback_node(state: MasterGraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Handles business-level mitigation rules.
    """
    context = state["workflow_context"]
    agent_name = state["target_agent"]
    error_msg = state["transport_error"] or "Unknown error"
    
    fallback_engine = config["configurable"]["fallback_engine"]
    state_manager = config["configurable"]["state_manager"]
    timeline = config["configurable"]["timeline"]
    trace = config["configurable"]["trace"]
    
    # Run fallback mitigation
    fallback_applied = fallback_engine.execute_fallback(context, error_msg)
    
    if "proposed_fallback" in context.metadata:
        # Offline interview proposal requires pause
        timeline.add_milestone("Fallback proposed: Switch to Offline mode")
        state_manager.update_state(context.workflow_id, STATE_WORKFLOW_PAUSED, current_step=f"Error_{agent_name}_Paused")
        trace.final_status = "PAUSED"
        timeline.add_milestone("Workflow paused awaiting fallback approval.")
        
        return {
            "workflow_context": context,
            "graph_status": "PAUSED"
        }
        
    # Unmitigated terminal failure
    timeline.add_milestone("All retry and fallback policies exhausted. Workflow failed.")
    state_manager.update_state(context.workflow_id, STATE_WORKFLOW_PAUSED, current_step=f"Error_{agent_name}_Paused")
    trace.final_status = "PAUSED"
    
    return {
        "workflow_context": context,
        "graph_status": "FAILED"
    }

def human_approval_node(state: MasterGraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Gate keeping node for manual checkpoint interrupts.
    """
    context = state["workflow_context"]
    approval_engine = config["configurable"]["approval_engine"]
    timeline = config["configurable"]["timeline"]
    event_store = config["configurable"]["event_store"]
    state_manager = config["configurable"]["state_manager"]
    trace = config["configurable"]["trace"]
    
    # 1. First Entry Check: Determine if approval is requested
    pending_next_state = context.metadata.pop("pending_next_state", None)
    paused_approval = context.metadata.pop("paused_on_approval", None)
    
    if pending_next_state:
        # User has resumed and approved
        context.previous_state = context.current_state
        context.current_state = pending_next_state
        
        state_manager.update_state(context.workflow_id, pending_next_state, current_step="Process_WorkflowResumed")
        timeline.add_milestone(f"Human Approval Granted: {paused_approval}")
        timeline.add_milestone(f"Workflow Resumed to State: {pending_next_state}")
        
        # Log resumes
        from shared.events.base_event import BaseEvent
        resume_event = BaseEvent(name="WorkflowResumed", candidate_id=context.candidate.candidate_id)
        event_store.log_event(resume_event, "Completed")
        
        if pending_next_state == STATE_OFFER_PIPELINE_TRIGGERED:
            status = "WORKFLOW_COMPLETED"
        else:
            status = "EVENT_COMPLETED"
            
        return {
            "workflow_context": context,
            "next_state": pending_next_state,
            "target_agent": None,
            "graph_status": status
        }
        
    # First entry: process and flag pause
    next_state = state["next_state"]
    approval_type = approval_engine.process_approval(context.current_state, next_state, context)
    timeline.add_milestone(f"Workflow Paused on Approval: {approval_type}")
    
    return {
        "workflow_context": context,
        "graph_status": "PAUSED"
    }

def finalize_node(state: MasterGraphState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Cleans up execution timelines and closes trace lifecycles.
    """
    context = state["workflow_context"]
    trace = config["configurable"]["trace"]
    timeline = config["configurable"]["timeline"]
    status = state["graph_status"]
    
    if status == "WORKFLOW_COMPLETED":
        trace.end_time = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        if context.current_state == STATE_OFFER_PIPELINE_TRIGGERED:
            trace.final_status = "COMPLETED"
            timeline.add_milestone("Workflow completed and handed off to Pipeline-3")
        else:
            trace.final_status = "REJECTED"
            
    return {}
