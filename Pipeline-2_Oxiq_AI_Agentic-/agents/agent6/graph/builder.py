from langgraph.graph import StateGraph, START, END
from agents.agent6.graph.state import Agent6GraphState
from agents.agent6.graph.nodes import (
    intake_node, validate_node, retrieve_resume_node, retrieve_database_context_node,
    select_mode_node, select_interviewer_node, select_slot_node, reserve_calendar_node,
    create_meet_node, build_interview_node, generate_document_node, prepare_database_node,
    commit_database_node, send_notification_node, build_response_node
)
from agents.agent6.graph.edges import (
    route_after_intake, route_after_validate, route_after_resume, route_after_db_read,
    route_after_interviewer, route_after_slot, route_after_calendar, route_after_meet,
    route_after_document, route_after_commit, route_after_notification
)

def compile_agent_graph():
    """
    Assembles and compiles the stateless Agent 6 scheduling orchestrator graph.
    """
    workflow = StateGraph(Agent6GraphState)
    
    # 1. Register Nodes
    workflow.add_node("intake_node", intake_node)
    workflow.add_node("validate_node", validate_node)
    workflow.add_node("retrieve_resume_node", retrieve_resume_node)
    workflow.add_node("retrieve_database_context_node", retrieve_database_context_node)
    workflow.add_node("select_mode_node", select_mode_node)
    workflow.add_node("select_interviewer_node", select_interviewer_node)
    workflow.add_node("select_slot_node", select_slot_node)
    workflow.add_node("reserve_calendar_node", reserve_calendar_node)
    workflow.add_node("create_meet_node", create_meet_node)
    workflow.add_node("build_interview_node", build_interview_node)
    workflow.add_node("generate_document_node", generate_document_node)
    workflow.add_node("prepare_database_node", prepare_database_node)
    workflow.add_node("commit_database_node", commit_database_node)
    workflow.add_node("send_notification_node", send_notification_node)
    workflow.add_node("build_response_node", build_response_node)
    
    # 2. Add Static Edges
    workflow.add_edge(START, "intake_node")
    workflow.add_edge("select_mode_node", "select_interviewer_node")
    workflow.add_edge("build_interview_node", "generate_document_node")
    workflow.add_edge("prepare_database_node", "commit_database_node")
    workflow.add_edge("build_response_node", END)
    
    # 3. Add Conditional Edges
    workflow.add_conditional_edges(
        "intake_node",
        route_after_intake,
        {
            "validate_node": "validate_node",
            "build_response_node": "build_response_node"
        }
    )
    
    workflow.add_conditional_edges(
        "validate_node",
        route_after_validate,
        {
            "retrieve_resume_node": "retrieve_resume_node",
            "build_response_node": "build_response_node"
        }
    )
    
    workflow.add_conditional_edges(
        "retrieve_resume_node",
        route_after_resume,
        {
            "retrieve_database_context_node": "retrieve_database_context_node",
            "build_response_node": "build_response_node"
        }
    )
    
    workflow.add_conditional_edges(
        "retrieve_database_context_node",
        route_after_db_read,
        {
            "select_mode_node": "select_mode_node",
            "retrieve_database_context_node": "retrieve_database_context_node",
            "build_response_node": "build_response_node"
        }
    )
    
    workflow.add_conditional_edges(
        "select_interviewer_node",
        route_after_interviewer,
        {
            "select_slot_node": "select_slot_node",
            "build_response_node": "build_response_node"
        }
    )
    
    workflow.add_conditional_edges(
        "select_slot_node",
        route_after_slot,
        {
            "reserve_calendar_node": "reserve_calendar_node",
            "build_response_node": "build_response_node"
        }
    )
    
    workflow.add_conditional_edges(
        "reserve_calendar_node",
        route_after_calendar,
        {
            "create_meet_node": "create_meet_node",
            "build_interview_node": "build_interview_node",
            "reserve_calendar_node": "reserve_calendar_node",
            "build_response_node": "build_response_node"
        }
    )
    
    workflow.add_conditional_edges(
        "create_meet_node",
        route_after_meet,
        {
            "build_interview_node": "build_interview_node",
            "create_meet_node": "create_meet_node",
            "build_response_node": "build_response_node"
        }
    )
    
    workflow.add_conditional_edges(
        "generate_document_node",
        route_after_document,
        {
            "prepare_database_node": "prepare_database_node",
            "generate_document_node": "generate_document_node",
            "build_response_node": "build_response_node"
        }
    )
    
    workflow.add_conditional_edges(
        "commit_database_node",
        route_after_commit,
        {
            "send_notification_node": "send_notification_node",
            "build_response_node": "build_response_node"
        }
    )
    
    workflow.add_conditional_edges(
        "send_notification_node",
        route_after_notification,
        {
            "build_response_node": "build_response_node",
            "send_notification_node": "send_notification_node"
        }
    )
    
    return workflow.compile()
