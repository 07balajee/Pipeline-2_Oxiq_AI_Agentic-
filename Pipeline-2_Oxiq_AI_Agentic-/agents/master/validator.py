from typing import Any, Dict
from pydantic import ValidationError
from schemas.candidate import CandidateModel
from schemas.job import JobModel
from schemas.agent_response import AgentResponse
from schemas.workflow_state import WorkflowStateModel
from shared.logger.logger import error_logger

class Validator:
    """
    Validates input and output schemas against strict Pydantic definitions
    to prevent processing of malformed data inside the pipeline.
    """

    @staticmethod
    def validate_candidate(data: Dict[str, Any]) -> CandidateModel:
        """
        Validates Candidate input payloads.
        """
        try:
            return CandidateModel.model_validate(data)
        except ValidationError as e:
            error_logger.error("Candidate validation failed", metadata={"errors": e.errors()})
            raise

    @staticmethod
    def validate_job(data: Dict[str, Any]) -> JobModel:
        """
        Validates Job criteria parameters.
        """
        try:
            return JobModel.model_validate(data)
        except ValidationError as e:
            error_logger.error("Job validation failed", metadata={"errors": e.errors()})
            raise

    @staticmethod
    def validate_agent_response(data: Dict[str, Any]) -> AgentResponse:
        """
        Validates output responses returned by worker agents.
        """
        try:
            return AgentResponse.model_validate(data)
        except ValidationError as e:
            error_logger.error("Agent response validation failed", metadata={"errors": e.errors()})
            raise

    @staticmethod
    def validate_workflow_state(data: Dict[str, Any]) -> WorkflowStateModel:
        """
        Validates execution state properties.
        """
        try:
            return WorkflowStateModel.model_validate(data)
        except ValidationError as e:
            error_logger.error("Workflow state validation failed", metadata={"errors": e.errors()})
            raise
