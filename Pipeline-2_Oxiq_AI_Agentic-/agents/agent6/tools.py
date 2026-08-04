from typing import Any, Dict
from shared.registry.tool_registry import tool_registry
from schemas.mcp_response import MCPResponse

class Agent6ToolsAdapter:
    """
    Thin adapter class mapping scheduling helper invocations to corresponding
    MCP Client instances resolved dynamically from the ToolRegistry.
    """

    @staticmethod
    def get_resume_summary(resume_url: str, workflow_id: str, metadata: Dict[str, Any] = None) -> MCPResponse:
        client_cls = tool_registry.get_tool("resume_mcp")
        return client_cls().execute(
            action="get_resume_summary",
            resume_url=resume_url,
            workflow_id=workflow_id,
            metadata=metadata
        )

    @staticmethod
    def read_candidate(candidate_id: str, workflow_id: str, metadata: Dict[str, Any] = None) -> MCPResponse:
        client_cls = tool_registry.get_tool("database_mcp")
        return client_cls().execute(
            action="read_candidate",
            candidate_id=candidate_id,
            workflow_id=workflow_id,
            metadata=metadata
        )

    @staticmethod
    def read_job(job_id: str, workflow_id: str, metadata: Dict[str, Any] = None) -> MCPResponse:
        client_cls = tool_registry.get_tool("database_mcp")
        return client_cls().execute(
            action="read_job",
            job_id=job_id,
            workflow_id=workflow_id,
            metadata=metadata
        )

    @staticmethod
    def fetch_calendar_availability(interviewer_id: str, workflow_id: str, metadata: Dict[str, Any] = None) -> MCPResponse:
        client_cls = tool_registry.get_tool("calendar_mcp")
        return client_cls().execute(
            action="fetch_availability",
            interviewer_id=interviewer_id,
            workflow_id=workflow_id,
            metadata=metadata
        )

    @staticmethod
    def reserve_slot(slot_id: str, interviewer_name: str, workflow_id: str, idempotency_key: str = None, metadata: Dict[str, Any] = None) -> MCPResponse:
        client_cls = tool_registry.get_tool("calendar_mcp")
        return client_cls().execute(
            action="reserve_slot",
            slot_id=slot_id,
            interviewer_name=interviewer_name,
            workflow_id=workflow_id,
            idempotency_key=idempotency_key,
            metadata=metadata
        )

    @staticmethod
    def generate_meeting(workflow_id: str, idempotency_key: str = None, metadata: Dict[str, Any] = None) -> MCPResponse:
        client_cls = tool_registry.get_tool("meet_mcp")
        return client_cls().execute(
            action="generate_meeting",
            workflow_id=workflow_id,
            idempotency_key=idempotency_key,
            metadata=metadata
        )

    @staticmethod
    def generate_interview_packet(interview_details: Dict[str, Any], workflow_id: str, idempotency_key: str = None, metadata: Dict[str, Any] = None) -> MCPResponse:
        client_cls = tool_registry.get_tool("document_mcp")
        return client_cls().execute(
            action="generate_interview_packet",
            interview_details=interview_details,
            workflow_id=workflow_id,
            idempotency_key=idempotency_key,
            metadata=metadata
        )

    @staticmethod
    def send_notification(recipient: str, subject: str, body: str, workflow_id: str, idempotency_key: str = None, metadata: Dict[str, Any] = None) -> MCPResponse:
        client_cls = tool_registry.get_tool("notification_mcp")
        return client_cls().execute(
            action="send_notification",
            recipient=recipient,
            subject=subject,
            body=body,
            workflow_id=workflow_id,
            idempotency_key=idempotency_key,
            metadata=metadata
        )

    @staticmethod
    def prepare_database_payload(candidate_id: str, interviewer_id: str, scheduled_time: str, workflow_id: str, idempotency_key: str = None, metadata: Dict[str, Any] = None) -> MCPResponse:
        client_cls = tool_registry.get_tool("database_mcp")
        return client_cls().execute(
            action="prepare_interview",
            candidate_id=candidate_id,
            interviewer_id=interviewer_id,
            scheduled_time=scheduled_time,
            workflow_id=workflow_id,
            idempotency_key=idempotency_key,
            metadata=metadata
        )

    @staticmethod
    def prepare_candidate_update(candidate_id: str, new_state: str, workflow_id: str, idempotency_key: str = None, metadata: Dict[str, Any] = None) -> MCPResponse:
        client_cls = tool_registry.get_tool("database_mcp")
        return client_cls().execute(
            action="prepare_update",
            candidate_id=candidate_id,
            new_state=new_state,
            workflow_id=workflow_id,
            idempotency_key=idempotency_key,
            metadata=metadata
        )

    @staticmethod
    def commit_transaction(prepared_payload: Dict[str, Any], workflow_id: str, metadata: Dict[str, Any] = None) -> MCPResponse:
        client_cls = tool_registry.get_tool("database_mcp")
        return client_cls().execute(
            action="commit",
            prepared_payload=prepared_payload,
            workflow_id=workflow_id,
            metadata=metadata
        )

    @staticmethod
    def rollback_transaction(prepared_payload: Dict[str, Any], workflow_id: str, metadata: Dict[str, Any] = None) -> MCPResponse:
        client_cls = tool_registry.get_tool("database_mcp")
        return client_cls().execute(
            action="rollback",
            prepared_payload=prepared_payload,
            workflow_id=workflow_id,
            metadata=metadata
        )
