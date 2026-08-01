from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from agents.master.graph.state import MasterGraphState
from agents.master.graph.nodes import (
    intake_node,
    route_node,
    dispatch_node,
    response_validation_node,
    state_transition_node,
    retry_node,
    fallback_node,
    human_approval_node,
    finalize_node
)
from agents.master.graph.edges import (
    route_decision_edge,
    post_transition_edge,
    dispatch_decision_edge,
    retry_decision_edge,
    fallback_decision_edge,
    validation_decision_edge
)

def compile_workflow_graph():
    """
    Builds and compiles the Master Agent LangGraph orchestrator.
    Configures an in-memory MemorySaver checkpointer and schedules Human Approval interrupts.
    """
    workflow = StateGraph(MasterGraphState)
    
    # 1. Register Graph Nodes
    workflow.add_node("intake_node", intake_node)
    workflow.add_node("route_node", route_node)
    workflow.add_node("dispatch_node", dispatch_node)
    workflow.add_node("response_validation_node", response_validation_node)
    workflow.add_node("state_transition_node", state_transition_node)
    workflow.add_node("retry_node", retry_node)
    workflow.add_node("fallback_node", fallback_node)
    workflow.add_node("human_approval_node", human_approval_node)
    workflow.add_node("finalize_node", finalize_node)
    
    # 2. Setup Static Edge Connections
    workflow.add_edge(START, "intake_node")
    workflow.add_edge("intake_node", "route_node")
    workflow.add_edge("finalize_node", END)
    
    # 3. Setup Conditional Routing Edges
    workflow.add_conditional_edges(
        "route_node",
        route_decision_edge,
        {
            "human_approval_node": "human_approval_node",
            "state_transition_node": "state_transition_node"
        }
    )
    
    workflow.add_conditional_edges(
        "state_transition_node",
        post_transition_edge,
        {
            "dispatch_node": "dispatch_node",
            "finalize_node": "finalize_node"
        }
    )
    
    workflow.add_conditional_edges(
        "dispatch_node",
        dispatch_decision_edge,
        {
            "response_validation_node": "response_validation_node",
            "retry_node": "retry_node"
        }
    )
    
    workflow.add_conditional_edges(
        "response_validation_node",
        validation_decision_edge,
        {
            "retry_node": "retry_node",
            "finalize_node": "finalize_node"
        }
    )
    
    workflow.add_conditional_edges(
        "retry_node",
        retry_decision_edge,
        {
            "route_node": "route_node",
            "fallback_node": "fallback_node"
        }
    )
    
    workflow.add_conditional_edges(
        "fallback_node",
        fallback_decision_edge,
        {
            "human_approval_node": "human_approval_node",
            "finalize_node": "finalize_node"
        }
    )
    
    # After resuming from human approval, run transition sequence directly to finalization
    workflow.add_edge("human_approval_node", "finalize_node")
    
    # 4. Compile with Memory Checkpointer and interrupts
    memory_saver = MemorySaver()
    compiled_app = workflow.compile(
        checkpointer=memory_saver,
        interrupt_before=["human_approval_node"]
    )
    
    return compiled_app
