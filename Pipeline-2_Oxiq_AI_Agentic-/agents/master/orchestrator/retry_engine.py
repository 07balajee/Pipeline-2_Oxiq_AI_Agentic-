from shared.config.constants import MAX_RETRY_ATTEMPTS
from shared.context.workflow_context import WorkflowContext
from shared.logger.logger import workflow_logger, error_logger

class RetryEngine:
    """
    Evaluates execution failures, tracking retries against MAX_RETRY_ATTEMPTS rules.
    Decides whether to re-attempt or bubble failure to Fallback/Error engines.
    """

    def should_retry(self, context: WorkflowContext) -> bool:
        """
        Determines if the workflow execution is allowed to attempt another retry.
        """
        current_retries = context.metadata.get("retry_count", 0)
        
        if current_retries < MAX_RETRY_ATTEMPTS:
            workflow_logger.info(
                f"Evaluation failed. Attempting retry {current_retries + 1} of {MAX_RETRY_ATTEMPTS}...",
                trace_id=context.workflow_id
            )
            return True
            
        error_logger.error(
            f"Maximum retry threshold ({MAX_RETRY_ATTEMPTS}) reached. Aborting retries.",
            trace_id=context.workflow_id
        )
        return False

    def increment_retry_count(self, context: WorkflowContext) -> int:
        """
        Increments the retry counter stored in the workflow context metadata.
        """
        current = context.metadata.get("retry_count", 0)
        new_count = current + 1
        context.metadata["retry_count"] = new_count
        return new_count

    def reset_retry_count(self, context: WorkflowContext):
        """
        Resets retry counter to 0 on successful step completion.
        """
        context.metadata["retry_count"] = 0
