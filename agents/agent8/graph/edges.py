from agents.agent8.graph.state import Agent8GraphState

def route_after_validation(state: Agent8GraphState) -> str:
    if state.get("last_error"):
        return "build_response_node"
    return "retrieve_context_node"

def route_after_retrieval(state: Agent8GraphState) -> str:
    if state.get("route_action") == "RETRY":
        return "retrieve_context_node"
    if state.get("last_error"):
        return "build_response_node"
    return "evaluate_hr_node"

def route_after_evaluation(state: Agent8GraphState) -> str:
    if state.get("last_error"):
        return "build_response_node"
    return "calculate_ranking_node"

def route_after_ranking(state: Agent8GraphState) -> str:
    if state.get("last_error"):
        return "build_response_node"
    return "prepare_database_node"

def route_after_db_prep(state: Agent8GraphState) -> str:
    if state.get("last_error"):
        return "build_response_node"
    return "commit_database_node"

def route_after_commit(state: Agent8GraphState) -> str:
    if state.get("route_action") == "RETRY":
        return "commit_database_node"
    return "build_response_node"
