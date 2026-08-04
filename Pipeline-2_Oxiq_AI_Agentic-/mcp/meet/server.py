import time
import uuid
from mcp.meet.mock import get_mock_meet_url
from schemas.mcp_response import MCPResponse

class MeetMCPServer:
    """
    Mock Meet MCP Server simulating virtual meeting creation and configuration.
    """

    def generate_meeting(self, workflow_id: str) -> MCPResponse:
        start_time = time.time()
        time.sleep(0.02)
        trace_id = str(uuid.uuid4())
        meet_url = get_mock_meet_url(workflow_id)
        
        return MCPResponse(
            status="SUCCESS",
            mcp_name="MeetMCP",
            workflow_id=workflow_id,
            trace_id=trace_id,
            execution_time_ms=(time.time() - start_time) * 1000,
            payload={
                "meeting_url": meet_url,
                "access_code": f"cod-{workflow_id[:4]}",
                "settings": {"recording_enabled": True}
            }
        )
