from shared.context.workflow_context import WorkflowContext
from shared.logger.logger import workflow_logger

class FallbackEngine:
    """
    Evaluates context failures and applies predefined architectural mitigation paths.
    Enables resilient execution transitions (e.g. falling back to Offline mode).
    """

    def execute_fallback(self, context: WorkflowContext, failure_reason: str) -> bool:
        """
        Triggers fallback transitions based on current run context.
        
        Returns:
            bool: True if a fallback path was applied immediately, False if human intervention is required.
        """
        candidate_name = context.candidate.name
        workflow_logger.info(
            f"Initiating fallback evaluation for candidate {candidate_name}. Reason: {failure_reason}",
            trace_id=context.workflow_id
        )

        current_mode = context.step_data.get("interview_mode") or context.metadata.get("interview_mode") or "Online"
        last_error = (context.metadata.get("last_execution_error") or "").lower()
        if current_mode == "Online" and (
            "meet" in failure_reason.lower() or "google meet" in failure_reason.lower() or
            "meet" in last_error or "google meet" in last_error
        ):
            workflow_logger.logger.warning(
                f"Virtual meeting creation failed. Proposing fallback: Offline Interview mode."
            )
            # Store proposed fallback and failure context in metadata
            context.metadata["proposed_fallback"] = "Offline Interview"
            context.metadata["failure_reason"] = "Google Meet generation"
            context.metadata["fallback_applied"] = True
            # Return False so that workflow is paused (requiring manual resume / approval)
            return False

        return False
