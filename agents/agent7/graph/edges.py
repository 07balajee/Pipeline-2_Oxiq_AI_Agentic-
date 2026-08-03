from agents.agent7.graph.state import Agent7GraphState

def route_after_validation(state: Agent7GraphState) -> str:
    if state.get("last_error"):
        return "build_response_node"
    return "retrieve_context_node"

def route_after_retrieval(state: Agent7GraphState) -> str:
    if state.get("route_action") == "RETRY":
        return "retrieve_context_node"
    if state.get("last_error"):
        return "build_response_node"
    return "evaluate_technical_node"

def route_after_evaluation(state: Agent7GraphState) -> str:
    if state.get("last_error"):
        return "build_response_node"
    return "prepare_database_node"

def route_after_db_prep(state: Agent7GraphState) -> str:
    if state.get("last_error"):
        return "build_response_node"
    return "commit_database_node"

def route_after_commit(state: Agent7GraphState) -> str:
    if state.get("route_action") == "RETRY":
        return "commit_database_node"
    return "build_response_node"
