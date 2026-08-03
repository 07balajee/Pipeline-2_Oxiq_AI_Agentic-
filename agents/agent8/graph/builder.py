from langgraph.graph import StateGraph, START, END
from agents.agent8.graph.state import Agent8GraphState
from agents.agent8.graph.nodes import (
    intake_node, validate_context_node, retrieve_context_node,
    evaluate_hr_node, calculate_ranking_node, prepare_database_node,
    commit_database_node, build_response_node
)
from agents.agent8.graph.edges import (
    route_after_validation, route_after_retrieval, route_after_evaluation,
    route_after_ranking, route_after_db_prep, route_after_commit
)

def compile_agent_graph():
    """
    Assembles and compiles the stateless Agent 8 HR evaluation & ranking graph.
    """
    workflow = StateGraph(Agent8GraphState)
    
    # 1. Register Nodes
    workflow.add_node("intake_node", intake_node)
    workflow.add_node("validate_context_node", validate_context_node)
    workflow.add_node("retrieve_context_node", retrieve_context_node)
    workflow.add_node("evaluate_hr_node", evaluate_hr_node)
    workflow.add_node("calculate_ranking_node", calculate_ranking_node)
    workflow.add_node("prepare_database_node", prepare_database_node)
    workflow.add_node("commit_database_node", commit_database_node)
    workflow.add_node("build_response_node", build_response_node)
    
    # 2. Add Static Edges
    workflow.add_edge(START, "intake_node")
    workflow.add_edge("intake_node", "validate_context_node")
    workflow.add_edge("build_response_node", END)
    
    # 3. Add Conditional Edges
    workflow.add_conditional_edges(
        "validate_context_node",
        route_after_validation,
        {
            "retrieve_context_node": "retrieve_context_node",
            "build_response_node": "build_response_node"
        }
    )
    
    workflow.add_conditional_edges(
        "retrieve_context_node",
        route_after_retrieval,
        {
            "retrieve_context_node": "retrieve_context_node",
            "evaluate_hr_node": "evaluate_hr_node",
            "build_response_node": "build_response_node"
        }
    )
    
    workflow.add_conditional_edges(
        "evaluate_hr_node",
        route_after_evaluation,
        {
            "calculate_ranking_node": "calculate_ranking_node",
            "build_response_node": "build_response_node"
        }
    )
    
    workflow.add_conditional_edges(
        "calculate_ranking_node",
        route_after_ranking,
        {
            "prepare_database_node": "prepare_database_node",
            "build_response_node": "build_response_node"
        }
    )
    
    workflow.add_conditional_edges(
        "prepare_database_node",
        route_after_db_prep,
        {
            "commit_database_node": "commit_database_node",
            "build_response_node": "build_response_node"
        }
    )
    
    workflow.add_conditional_edges(
        "commit_database_node",
        route_after_commit,
        {
            "commit_database_node": "commit_database_node",
            "build_response_node": "build_response_node"
        }
    )
    
    return workflow.compile()
