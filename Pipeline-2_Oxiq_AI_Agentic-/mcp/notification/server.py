import time
import uuid
from mcp.notification.mock import get_mock_notification_result
from schemas.mcp_response import MCPResponse

class NotificationMCPServer:
    """
    Mock Notification MCP Server simulating communication dispatches.
    """

    def send_notification(self, recipient: str, subject: str, body: str, workflow_id: str) -> MCPResponse:
        start_time = time.time()
        time.sleep(0.03)
        trace_id = str(uuid.uuid4())
        payload = get_mock_notification_result(recipient)
        
        return MCPResponse(
            status="SUCCESS",
            mcp_name="NotificationMCP",
            workflow_id=workflow_id,
            trace_id=trace_id,
            execution_time_ms=(time.time() - start_time) * 1000,
            payload=payload,
            metadata={"subject": subject}
        )
