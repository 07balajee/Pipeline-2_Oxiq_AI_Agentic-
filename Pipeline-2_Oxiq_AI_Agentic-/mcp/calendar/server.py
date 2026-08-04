import time
import uuid
from mcp.calendar.mock import get_mock_availability
from schemas.mcp_response import MCPResponse

class CalendarMCPServer:
    """
    Mock Calendar MCP Server simulating availability checks and reservations.
    """

    def fetch_availability(self, interviewer_id: str, workflow_id: str) -> MCPResponse:
        start_time = time.time()
        time.sleep(0.03)
        trace_id = str(uuid.uuid4())
        payload = get_mock_availability(interviewer_id)
        
        return MCPResponse(
            status="SUCCESS",
            mcp_name="CalendarMCP",
            workflow_id=workflow_id,
            trace_id=trace_id,
            execution_time_ms=(time.time() - start_time) * 1000,
            payload=payload
        )

    def reserve_slot(self, slot_id: str, interviewer_name: str, workflow_id: str) -> MCPResponse:
        start_time = time.time()
        time.sleep(0.04)
        trace_id = str(uuid.uuid4())
        payload = {
            "booking_id": f"bk-{workflow_id[:6]}",
            "slot_id": slot_id,
            "interviewer": interviewer_name,
            "confirmed": True
        }
        return MCPResponse(
            status="SUCCESS",
            mcp_name="CalendarMCP",
            workflow_id=workflow_id,
            trace_id=trace_id,
            execution_time_ms=(time.time() - start_time) * 1000,
            payload=payload
        )
