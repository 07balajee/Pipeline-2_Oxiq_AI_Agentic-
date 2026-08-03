from shared.interfaces.agent import Agent
from schemas.agent_response import AgentResponse
from shared.context.workflow_context import WorkflowContext
from agents.agent7.graph import compile_agent_graph

class TechnicalInterviewAgent(Agent):
    """
    Technical Interview Assessment Agent (Agent 7).
    Evaluates candidate technical competencies, parses scorecards,
    and records results via internal LangGraph orchestration.
    """
    def __init__(self):
        self.graph = compile_agent_graph()

    def run(self, context: WorkflowContext) -> AgentResponse:
        """
        Runs the technical evaluation workflow using the stateless compiled LangGraph.
        """
        try:
            context.metadata.pop("last_execution_error", None)
            
            # Construct initial graph state statelessly
            initial_state = {
                "workflow_context": context,
                "candidate_context": None,
                "job_context": None,
                "technical_scores": None,
                "technical_recommendation": None,
                "db_scorecard_prepared": None,
                "retry_counts": {},
                "last_error": None,
                "failure_category": None,
                "failed_operation": None,
                "route_action": None,
                "warnings": [],
                "agent_response": None
            }
            
            # Invoke stateless graph execution
            final_state = self.graph.invoke(initial_state)
            
            # Sync modifications back to the caller's context reference in-place
            updated_ctx = final_state.get("workflow_context")
            if updated_ctx:
                context.step_data.update(updated_ctx.step_data)
                context.metadata.update(updated_ctx.metadata)
                context.current_state = updated_ctx.current_state
                context.previous_state = updated_ctx.previous_state
            
            response = final_state.get("agent_response")
            if not response:
                response = AgentResponse(
                    execution_status="FAILED",
                    errors=["No response returned from Agent 7 graph orchestration."],
                    summary="No response returned from Agent 7 graph orchestration."
                )
                
            if response.execution_status != "SUCCESS":
                err_msg = response.errors[0] if response.errors else "Unknown failure"
                context.metadata["last_execution_error"] = err_msg
                
            return response
            
        except Exception as e:
            context.metadata["last_execution_error"] = str(e)
            return AgentResponse(
                execution_status="FAILED",
                errors=[str(e)],
                summary=f"Execution exception inside Agent 7 evaluation: {str(e)}"
            )
