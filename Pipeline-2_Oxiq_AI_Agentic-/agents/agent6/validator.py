from typing import List, Tuple
from shared.context.workflow_context import WorkflowContext
from shared.logger.logger import error_logger, workflow_logger

class Validator:
    """
    Validates Candidate Context parameters for Agent 6.
    Ensures all prerequisite profile fields exist before scheduling attempts begin.
    """

    def validate(self, context: WorkflowContext) -> Tuple[bool, List[str]]:
        """
        Validates CandidateContext attributes.
        
        Args:
            context (WorkflowContext): Current workflow context containing the candidate profile.
            
        Returns:
            Tuple[bool, List[str]]: A tuple of (is_valid, error_messages_list).
        """
        errors = []
        candidate = context.candidate
        
        if not candidate:
            errors.append("Candidate context is completely missing.")
            return False, errors

        # Standard requirements check
        if not getattr(candidate, "candidate_id", None):
            errors.append("Candidate ID is missing.")
        if not getattr(candidate, "name", None):
            errors.append("Candidate Name is missing.")
        if not getattr(candidate, "email", None):
            errors.append("Candidate Email is missing.")
        if not getattr(candidate, "job_id", None):
            errors.append("Job ID is missing.")
        if not getattr(candidate, "resume_url", None):
            errors.append("Resume URL/Reference is missing.")
            
        # Verify screening score exists and is a valid percentage range
        score = getattr(candidate, "screening_score", None)
        if score is None:
            errors.append("Screening Score is missing.")
        elif not isinstance(score, (int, float)) or not (0 <= score <= 100):
            errors.append("Screening Score must be a valid numeric percentage between 0 and 100.")

        # Check intake workflow state compliance
        allowed_states = ["CandidateShortlisted", "InterviewScheduling"]
        if context.current_state not in allowed_states:
            errors.append(
                f"Invalid workflow state for scheduling: '{context.current_state}'. "
                f"Expected one of: {allowed_states}."
            )

        # Prevent duplicate scheduling unless explicit reschedule flag is set
        if context.step_data.get("scheduled_time") and not context.metadata.get("is_reschedule"):
            errors.append("Candidate has already been scheduled for an interview.")

        is_valid = len(errors) == 0
        if not is_valid:
            error_logger.error(
                "Agent 6 context validation failed.",
                trace_id=context.workflow_id,
                metadata={"validation_errors": errors}
            )
        else:
            workflow_logger.info("Agent 6 Context Validation Passed.", trace_id=context.workflow_id)

        return is_valid, errors

    def validate_job_payload(self, job_payload: dict, workflow_id: str) -> Tuple[bool, List[str]]:
        """
        Validates the job details retrieved from Database MCP.
        """
        errors = []
        if not job_payload:
            errors.append("Job context details are missing.")
            return False, errors

        if not job_payload.get("job_id"):
            errors.append("Job ID is missing.")
        if not job_payload.get("job_title"):
            errors.append("Job Title is missing.")
        if job_payload.get("status") != "ACTIVE":
            errors.append(f"Job is not active (status: '{job_payload.get('status')}').")

        is_valid = len(errors) == 0
        if not is_valid:
            error_logger.error(
                "Agent 6 job validation failed.",
                trace_id=workflow_id,
                metadata={"job_errors": errors}
            )
        return is_valid, errors
