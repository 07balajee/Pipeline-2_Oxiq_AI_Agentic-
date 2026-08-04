from typing import Optional, Tuple
from agents.master.router import Router
from shared.context.workflow_context import WorkflowContext
from shared.logger.logger import workflow_logger

class WorkflowEngine:
    """
    Evaluates current state parameters and resolves the target worker agent.
    Acts as the main state machine coordinator.
    """
    def __init__(self):
        self.router = Router()

    def resolve_next_step(self, context: WorkflowContext, event_name: str) -> Tuple[str, Optional[str]]:
        """
        Determines next state and target agent using transition rules.
        """
        current_state = context.current_state
        next_state, target_agent = self.router.route(current_state, event_name)
        
        workflow_logger.info(
            f"Workflow engine evaluated transition: '{current_state}' -> '{next_state}' (Trigger: {event_name})",
            trace_id=context.workflow_id
        )
        return next_state, target_agent
