from typing import Any, Dict, List, Optional
from schemas.agent_response import AgentResponse

class ResponseBuilder:
    """
    Builder pattern implementation for compiling the standard AgentResponse.
    """
    def __init__(self):
        self._execution_status = "SUCCESS"
        self._generated_event = None
        self._updated_state = None
        self._summary = ""
        self._errors = []
        self._warnings = []
        self._suggested_action = None
        self._metadata = {}

    def with_status(self, status: str) -> "ResponseBuilder":
        self._execution_status = status
        return self

    def with_event_and_state(self, event: Optional[str], state: Optional[str]) -> "ResponseBuilder":
        self._generated_event = event
        self._updated_state = state
        return self

    def with_summary(self, summary: str) -> "ResponseBuilder":
        self._summary = summary
        return self

    def with_errors(self, errors: List[str]) -> "ResponseBuilder":
        self._errors = errors
        return self

    def with_warnings(self, warnings: List[str]) -> "ResponseBuilder":
        self._warnings = warnings
        return self

    def with_action(self, action: str) -> "ResponseBuilder":
        self._suggested_action = action
        return self

    def with_metadata(self, metadata: Dict[str, Any]) -> "ResponseBuilder":
        self._metadata = metadata
        return self

    def build(self) -> AgentResponse:
        """
        Assembles and returns the AgentResponse schema.
        """
        return AgentResponse(
            execution_status=self._execution_status,
            generated_event=self._generated_event,
            updated_state=self._updated_state,
            summary=self._summary,
            errors=self._errors,
            warnings=self._warnings,
            suggested_action=self._suggested_action,
            metadata=self._metadata
        )
