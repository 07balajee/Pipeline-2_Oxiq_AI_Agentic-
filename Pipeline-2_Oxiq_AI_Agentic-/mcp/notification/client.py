from typing import Any
from shared.interfaces.tool import Tool
from mcp.notification.server import NotificationMCPServer
from schemas.mcp_response import MCPResponse

class NotificationMCPClient(Tool):
    """
    Client driver connecting to the Notification MCP Server.
    """
    def __init__(self):
        self.server = NotificationMCPServer()

    def execute(self, action: str, *args: Any, **kwargs: Any) -> MCPResponse:
        """
        Routes email/message dispatch requests to the Notification server.
        """
        workflow_id = kwargs.get("workflow_id", "")
        if action == "send_notification":
            recipient = kwargs.get("recipient", "")
            subject = kwargs.get("subject", "")
            body = kwargs.get("body", "")
            return self.server.send_notification(recipient, subject, body, workflow_id)
        else:
            raise NotImplementedError(
                f"Action '{action}' is not supported by NotificationMCPClient."
            )
