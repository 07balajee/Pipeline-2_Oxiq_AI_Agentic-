from shared.interfaces.agent import Agent
from schemas.agent_response import AgentResponse
from shared.context.workflow_context import WorkflowContext
from agents.agent6.graph import compile_agent_graph

class InterviewInvitationAgent(Agent):
    """
    Interview Invitation & Scheduling Agent (Agent 6).
    Coordinates intake validation, interview modes, interviewer select roster,
    and timeslots selection, returning structured completion events via compiled LangGraph.
    """
    def __init__(self):
        self.graph = compile_agent_graph()

    def run(self, context: WorkflowContext) -> AgentResponse:
        """
        Runs the core scheduling logic workflow using the stateless compiled LangGraph.
        """
        try:
            context.metadata.pop("last_execution_error", None)
            
            # Construct initial graph state statelessly
            initial_state = {
                "workflow_context": context,
                "interview_mode": None,
                "selected_interviewer": None,
                "selected_slot": None,
                "interview_object": None,
                "db_update_prepared": None,
                "db_insert_prepared": None,
                "retry_counts": {},
                "last_error": None,
                "failure_category": None,
                "failed_operation": None,
                "warnings": [],
                "agent_response": None
            }
            
            # Invoke stateless graph execution
            final_state = self.graph.invoke(initial_state)
            
            # Sync modifications back to the caller's reference in-place
            updated_ctx = final_state.get("workflow_context")
            if updated_ctx:
                context.step_data.update(updated_ctx.step_data)
                context.metadata.update(updated_ctx.metadata)
                context.current_state = updated_ctx.current_state
                context.previous_state = updated_ctx.previous_state
            
            response = final_state.get("agent_response")
            if not response:
                from agents.agent6.response_builder import ResponseBuilder
                response = (
                    ResponseBuilder()
                    .with_status("FAILED")
                    .with_summary("No response returned from Agent 6 graph orchestration.")
                    .build()
                )
                
            if response.execution_status != "SUCCESS":
                err_msg = response.errors[0] if response.errors else "Unknown failure"
                context.metadata["last_execution_error"] = err_msg
                
            return response
            
        except Exception as e:
            context.metadata["last_execution_error"] = str(e)
            from agents.agent6.response_builder import ResponseBuilder
            return (
                ResponseBuilder()
                .with_status("FAILED")
                .with_errors([str(e)])
                .with_summary("Execution exception inside Agent 6 scheduling.")
                .build()
            )
