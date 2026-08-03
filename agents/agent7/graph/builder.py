from langgraph.graph import StateGraph, START, END
from agents.agent7.graph.state import Agent7GraphState
from agents.agent7.graph.nodes import (
    intake_node, validate_context_node, retrieve_context_node,
    evaluate_technical_node, prepare_database_node, commit_database_node,
    build_response_node
)
from agents.agent7.graph.edges import (
    route_after_validation, route_after_retrieval, route_after_evaluation,
    route_after_db_prep, route_after_commit
)

def compile_agent_graph():
    """
    Assembles and compiles the stateless Agent 7 technical evaluation graph.
    """
    workflow = StateGraph(Agent7GraphState)
    
    # 1. Register Nodes
    workflow.add_node("intake_node", intake_node)
    workflow.add_node("validate_context_node", validate_context_node)
    workflow.add_node("retrieve_context_node", retrieve_context_node)
    workflow.add_node("evaluate_technical_node", evaluate_technical_node)
    workflow.add_node("prepare_database_node", prepare_database_node)
    workflow.add_node("commit_database_node", commit_database_node)
    workflow.add_node("build_response_node", build_response_node)
    
    # 2. Add Static Edges
    workflow.add_edge(START, "intake_node")
    workflow.add_edge("intake_node", "validate_context_node")
    workflow.add_edge("evaluate_technical_node", "prepare_database_node")
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
            "evaluate_technical_node": "evaluate_technical_node",
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
