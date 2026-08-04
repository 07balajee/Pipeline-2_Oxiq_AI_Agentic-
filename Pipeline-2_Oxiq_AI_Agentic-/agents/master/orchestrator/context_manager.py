import uuid
from shared.events.base_event import BaseEvent
from shared.context.workflow_context import WorkflowContext
from shared.logger.logger import workflow_logger

class ContextManager:
    """
    Manages parameters decoration and context mapping before dispatching queries.
    Aggregates candidates contexts, traces, and dynamic event variables.
    """

    def prepare_execution_context(self, context: WorkflowContext, event: BaseEvent) -> WorkflowContext:
        """
        Enriches and returns the WorkflowContext before execution.
        """
        # Generate a unique task transaction trace ID
        trace_id = str(uuid.uuid4())
        
        # Decorate metadata parameters
        context.metadata["active_trace_id"] = trace_id
        context.metadata["last_event_name"] = event.name
        context.metadata["last_event_candidate_id"] = event.candidate_id
        
        if "retry_count" not in context.metadata:
            context.metadata["retry_count"] = 0

        workflow_logger.info(
            f"Context manager prepared variables | Active Trace ID: {trace_id} | State: {context.current_state}",
            trace_id=context.workflow_id
        )
        return context
