from typing import List, Tuple
from schemas.agent_response import AgentResponse
from shared.logger.logger import workflow_logger, error_logger

class ResponseValidator:
    """
    Validates the structure and semantic details of AgentResponses returned by worker agents.
    Ensures state machine transitions don't occur using invalid payloads.
    """

    def validate_response(self, agent_name: str, response: AgentResponse) -> Tuple[bool, List[str]]:
        """
        Validates AgentResponse attributes and schema requirements.
        
        Returns:
            Tuple[bool, List[str]]: (is_valid, validation_errors_list)
        """
        errors = []

        # 1. Base Class Validation
        if not isinstance(response, AgentResponse):
            errors.append("Response object is not a valid AgentResponse instance.")
            return False, errors

        # 2. Status check
        if response.execution_status != "SUCCESS":
            errors.append(f"Agent execution reported status: '{response.execution_status}'.")

        # 3. Payload variables presence
        if not response.generated_event:
            errors.append("AgentResponse is missing required attribute: 'generated_event'.")
        if not response.updated_state:
            errors.append("AgentResponse is missing required attribute: 'updated_state'.")

        # 4. Domain boundary validation
        if agent_name == "agent6":
            # Schedule agent requires compiled booking payloads in metadata
            meta = response.metadata or {}
            if not meta.get("candidate_id"):
                errors.append("Agent 6 metadata payload is missing 'candidate_id'.")
            if not meta.get("time_slot"):
                errors.append("Agent 6 metadata payload is missing 'time_slot'.")
            if not meta.get("interviewer_name"):
                errors.append("Agent 6 metadata payload is missing 'interviewer_name'.")

        is_valid = len(errors) == 0
        if not is_valid:
            error_logger.error(
                f"Response validation failed for {agent_name}.",
                metadata={"validation_errors": errors}
            )
        else:
            workflow_logger.info(f"Response validation successful for {agent_name}.")

        return is_valid, errors
