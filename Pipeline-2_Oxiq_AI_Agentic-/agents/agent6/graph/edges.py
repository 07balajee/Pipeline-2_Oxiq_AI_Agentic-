from agents.agent6.graph.state import Agent6GraphState
from agents.agent6.models import InterviewMode

def route_after_intake(state: Agent6GraphState) -> str:
    if state.get("last_error"):
        return "build_response_node"
    return "validate_node"

def route_after_validate(state: Agent6GraphState) -> str:
    if state.get("last_error"):
        return "build_response_node"
    return "retrieve_resume_node"

def route_after_resume(state: Agent6GraphState) -> str:
    if state.get("last_error"):
        return "build_response_node"
    return "retrieve_database_context_node"

def route_after_db_read(state: Agent6GraphState) -> str:
    if state.get("route_action") == "RETRY":
        return "retrieve_database_context_node"
    if state.get("last_error"):
        return "build_response_node"
    return "select_mode_node"

def route_after_interviewer(state: Agent6GraphState) -> str:
    if state.get("last_error"):
        return "build_response_node"
    return "select_slot_node"

def route_after_slot(state: Agent6GraphState) -> str:
    if state.get("last_error"):
        return "build_response_node"
    return "reserve_calendar_node"

def route_after_calendar(state: Agent6GraphState) -> str:
    if state.get("route_action") == "RETRY":
        return "reserve_calendar_node"
    if state.get("last_error"):
        return "build_response_node"
    mode = state.get("interview_mode")
    if mode == InterviewMode.ONLINE:
        return "create_meet_node"
    return "build_interview_node"

def route_after_meet(state: Agent6GraphState) -> str:
    if state.get("route_action") == "RETRY":
        return "create_meet_node"
    if state.get("last_error"):
        return "build_response_node"
    return "build_interview_node"

def route_after_document(state: Agent6GraphState) -> str:
    if state.get("route_action") == "RETRY":
        return "generate_document_node"
    if state.get("last_error"):
        return "build_response_node"
    return "prepare_database_node"

def route_after_commit(state: Agent6GraphState) -> str:
    if state.get("last_error"):
        return "build_response_node"
    return "send_notification_node"

def route_after_notification(state: Agent6GraphState) -> str:
    if state.get("route_action") == "RETRY":
        return "send_notification_node"
    return "build_response_node"
