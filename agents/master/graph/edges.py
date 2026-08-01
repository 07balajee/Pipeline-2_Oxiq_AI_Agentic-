from langchain_core.runnables import RunnableConfig
from agents.master.graph.state import MasterGraphState

def route_decision_edge(state: MasterGraphState, config: RunnableConfig) -> str:
    """
    Decides routing paths after state evaluation.
    """
    context = state["workflow_context"]
    next_state = state["next_state"]
    approval_engine = config["configurable"]["approval_engine"]
    
    # 1. Human Approval paused checkpoints
    if next_state and approval_engine.should_pause_for_approval(context.current_state, next_state, context):
        approval_type = "ManagerApproval"
        if context.current_state == "InterviewScheduling" and next_state == "InterviewScheduled":
            approval_type = "SlotApproval"
        elif context.current_state == "CandidateSelected" and next_state == "OfferPipelineTriggered":
            approval_type = "SelectionApproval"
        context.metadata["paused_on_approval"] = approval_type
        context.metadata["pending_next_state"] = next_state
        return "human_approval_node"
        
    # Always transition state first
    return "state_transition_node"

def post_transition_edge(state: MasterGraphState, config: RunnableConfig) -> str:
    """
    Routes execution to worker dispatch if target exists, or terminates event turn.
    """
    if state["target_agent"]:
        return "dispatch_node"
    return "finalize_node"

def dispatch_decision_edge(state: MasterGraphState, config: RunnableConfig) -> str:
    """
    Routes execution outcomes (success, business failures, transport errors).
    """
    err = state["transport_error"]
    
    if err:
        # Categorized transport failures trigger retries
        return "retry_node"
        
    # Otherwise validate response (which will handle success or business failure)
    return "response_validation_node"

def retry_decision_edge(state: MasterGraphState, config: RunnableConfig) -> str:
    """
    Decides between re-routing attempts or escalating to fallback paths.
    """
    if state["incoming_event"] == "RetryRequested":
        return "route_node"
    return "fallback_node"

def fallback_decision_edge(state: MasterGraphState, config: RunnableConfig) -> str:
    """
    Decides between pausing for fallback approvals or terminating workflows.
    """
    context = state["workflow_context"]
    if "proposed_fallback" in context.metadata:
        return "human_approval_node"
    return "finalize_node"

def validation_decision_edge(state: MasterGraphState, config: RunnableConfig) -> str:
    """
    Routes validation outcomes to retries if validation failed, or finalizes event loop.
    """
    if state["transport_error"]:
        return "retry_node"
    return "finalize_node"
