from shared.interfaces.agent import Agent
from schemas.agent_response import AgentResponse
from shared.context.workflow_context import WorkflowContext
from agents.agent6.scheduler import Scheduler

class InterviewInvitationAgent(Agent):
    """
    Interview Invitation & Scheduling Agent (Agent 6).
    Coordinates intake validation, interview modes, interviewer select roster,
    and timeslots selection, returning structured completion events.
    """
    def __init__(self):
        self.scheduler = Scheduler()

    def run(self, context: WorkflowContext) -> AgentResponse:
        """
        Runs the core scheduling logic workflow.
        """
        try:
            context.metadata.pop("last_execution_error", None)
            response = self.scheduler.run_scheduling_workflow(context)
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
