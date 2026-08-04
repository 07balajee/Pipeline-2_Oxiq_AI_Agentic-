import uuid
from typing import Any
from shared.interfaces.tool import Tool
from schemas.mcp_response import MCPResponse
from mcp.calendar.client import CalendarMCPClient
from mcp.meet.client import MeetMCPClient
from mcp.notification.client import NotificationMCPClient
from mcp.database.client import DatabaseMCPClient
from mcp.document.client import DocumentMCPClient
from mcp.resume.client import ResumeMCPClient

class FailableCalendarMCPClient(Tool):
    def __init__(self):
        self.underlying = CalendarMCPClient()

    def execute(self, *args: Any, **kwargs: Any) -> MCPResponse:
        metadata = kwargs.get("metadata") or {}
        workflow_id = kwargs.get("workflow_id", "")
        action = kwargs.get("action")

        if metadata.get("simulate_calendar_timeout_always"):
            return MCPResponse(
                status="FAILED",
                mcp_name="CalendarMCP",
                workflow_id=workflow_id,
                trace_id=str(uuid.uuid4()),
                execution_time_ms=10.0,
                errors=["Calendar connection timeout"]
            )
        if metadata.get("simulate_calendar_timeout_once"):
            retry_count = metadata.get("retry_count", 0)
            if retry_count == 0:
                return MCPResponse(
                    status="FAILED",
                    mcp_name="CalendarMCP",
                    workflow_id=workflow_id,
                    trace_id=str(uuid.uuid4()),
                    execution_time_ms=10.0,
                    errors=["Calendar connection timeout"]
                )
        if metadata.get("simulate_empty_slots"):
            if action == "fetch_availability" and kwargs.get("interviewer_id") == "int-1":
                return MCPResponse(
                    status="SUCCESS",
                    mcp_name="CalendarMCP",
                    workflow_id=workflow_id,
                    trace_id=str(uuid.uuid4()),
                    execution_time_ms=10.0,
                    payload=[]
                )
        if metadata.get("simulate_all_interviewers_unavailable"):
            if action == "fetch_availability":
                return MCPResponse(
                    status="SUCCESS",
                    mcp_name="CalendarMCP",
                    workflow_id=workflow_id,
                    trace_id=str(uuid.uuid4()),
                    execution_time_ms=10.0,
                    payload=[]
                )
        if metadata.get("simulate_calendar_failure"):
            return MCPResponse(
                status="FAILED",
                mcp_name="CalendarMCP",
                workflow_id=workflow_id,
                trace_id=str(uuid.uuid4()),
                execution_time_ms=10.0,
                errors=["Calendar internal error"]
            )
        if metadata.get("simulate_mcp_malformed"):
            if action == "fetch_availability":
                return MCPResponse(
                    status="SUCCESS",
                    mcp_name="CalendarMCP",
                    workflow_id=workflow_id,
                    trace_id=str(uuid.uuid4()),
                    execution_time_ms=10.0,
                    payload="Monday 10:00 AM" # Malformed: string instead of list
                )
        if metadata.get("simulate_slot_unavailable"):
            if action == "reserve_slot":
                return MCPResponse(
                    status="FAILED",
                    mcp_name="CalendarMCP",
                    workflow_id=workflow_id,
                    trace_id=str(uuid.uuid4()),
                    execution_time_ms=10.0,
                    errors=["Selected slot is no longer available"]
                )
        return self.underlying.execute(*args, **kwargs)

class FailableMeetMCPClient(Tool):
    def __init__(self):
        self.underlying = MeetMCPClient()

    def execute(self, *args: Any, **kwargs: Any) -> MCPResponse:
        metadata = kwargs.get("metadata") or {}
        workflow_id = kwargs.get("workflow_id", "")
        if metadata.get("simulate_meet_failure_always"):
            return MCPResponse(
                status="FAILED",
                mcp_name="MeetMCP",
                workflow_id=workflow_id,
                trace_id=str(uuid.uuid4()),
                execution_time_ms=10.0,
                errors=["Google Meet service unavailable"]
            )
          
        if metadata.get("simulate_meet_failure_once"):
            retry_count = metadata.get("retry_count", 0)
            if retry_count == 0:
                return MCPResponse(
                    status="FAILED",
                    mcp_name="MeetMCP",
                    workflow_id=workflow_id,
                    trace_id=str(uuid.uuid4()),
                    execution_time_ms=10.0,
                    errors=["Google Meet service unavailable"]
                )
        return self.underlying.execute(*args, **kwargs)

class FailableNotificationMCPClient(Tool):
    def __init__(self):
        self.underlying = NotificationMCPClient()

    def execute(self, *args: Any, **kwargs: Any) -> MCPResponse:
        metadata = kwargs.get("metadata") or {}
        workflow_id = kwargs.get("workflow_id", "")
        if metadata.get("simulate_notification_failure_always"):
            return MCPResponse(
                status="FAILED",
                mcp_name="NotificationMCP",
                workflow_id=workflow_id,
                trace_id=str(uuid.uuid4()),
                execution_time_ms=10.0,
                errors=["SMTP server timeout"]
            )
        if metadata.get("simulate_notification_failure_once"):
            retry_count = metadata.get("retry_count", 0)
            if retry_count == 0:
                return MCPResponse(
                    status="FAILED",
                    mcp_name="NotificationMCP",
                    workflow_id=workflow_id,
                    trace_id=str(uuid.uuid4()),
                    execution_time_ms=10.0,
                    errors=["SMTP server timeout"]
                )
        return self.underlying.execute(*args, **kwargs)

class FailableDatabaseMCPClient(Tool):
    def __init__(self):
        self.underlying = DatabaseMCPClient()

    def execute(self, *args: Any, **kwargs: Any) -> MCPResponse:
        metadata = kwargs.get("metadata") or {}
        workflow_id = kwargs.get("workflow_id", "")
        action = kwargs.get("action")

        if action in ["read_candidate", "read_job"]:
            if metadata.get("simulate_db_read_failure_always"):
                return MCPResponse(
                    status="FAILED",
                    mcp_name="DatabaseMCP",
                    workflow_id=workflow_id,
                    trace_id=str(uuid.uuid4()),
                    execution_time_ms=10.0,
                    errors=["Database read timeout"]
                )
            if metadata.get("simulate_db_read_failure_once"):
                retry_count = metadata.get("retry_count", 0)
                if retry_count == 0:
                    return MCPResponse(
                        status="FAILED",
                        mcp_name="DatabaseMCP",
                        workflow_id=workflow_id,
                        trace_id=str(uuid.uuid4()),
                        execution_time_ms=10.0,
                        errors=["Database read timeout"]
                    )
        if action == "commit":
            if metadata.get("simulate_db_write_failure"):
                return MCPResponse(
                    status="FAILED",
                    mcp_name="DatabaseMCP",
                    workflow_id=workflow_id,
                    trace_id=str(uuid.uuid4()),
                    execution_time_ms=10.0,
                    errors=["Database write deadlock"]
                )
        return self.underlying.execute(*args, **kwargs)

class FailableDocumentMCPClient(Tool):
    def __init__(self):
        self.underlying = DocumentMCPClient()

    def execute(self, *args: Any, **kwargs: Any) -> MCPResponse:
        metadata = kwargs.get("metadata") or {}
        workflow_id = kwargs.get("workflow_id", "")
        if metadata.get("simulate_doc_failure_always"):
            return MCPResponse(
                status="FAILED",
                mcp_name="DocumentMCP",
                workflow_id=workflow_id,
                trace_id=str(uuid.uuid4()),
                execution_time_ms=10.0,
                errors=["Document generator out of disk space"]
            )
        if metadata.get("simulate_doc_failure_once"):
            retry_count = metadata.get("retry_count", 0)
            if retry_count == 0:
                return MCPResponse(
                    status="FAILED",
                    mcp_name="DocumentMCP",
                    workflow_id=workflow_id,
                    trace_id=str(uuid.uuid4()),
                    execution_time_ms=10.0,
                    errors=["Document generator out of disk space"]
                )
        return self.underlying.execute(*args, **kwargs)

class FailableResumeMCPClient(Tool):
    def __init__(self):
        self.underlying = ResumeMCPClient()

    def execute(self, *args: Any, **kwargs: Any) -> MCPResponse:
        metadata = kwargs.get("metadata") or {}
        workflow_id = kwargs.get("workflow_id", "")
        if metadata.get("simulate_resume_failure"):
            return MCPResponse(
                status="FAILED",
                mcp_name="ResumeMCP",
                workflow_id=workflow_id,
                trace_id=str(uuid.uuid4()),
                execution_time_ms=10.0,
                errors=["Resume parser service down"]
            )
        return self.underlying.execute(*args, **kwargs)
