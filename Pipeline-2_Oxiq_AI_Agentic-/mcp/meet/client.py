from typing import Any
from shared.interfaces.tool import Tool
from mcp.meet.server import MeetMCPServer
from schemas.mcp_response import MCPResponse

class MeetMCPClient(Tool):
    """
    Client driver connecting to the Meet MCP Server.
    """
    def __init__(self):
        self.server = MeetMCPServer()

    def execute(self, action: str, *args: Any, **kwargs: Any) -> MCPResponse:
        """
        Routes conference room setup requests to the Meet server.
        """
        workflow_id = kwargs.get("workflow_id", "")
        if action == "generate_meeting":
            return self.server.generate_meeting(workflow_id)
        else:
            raise NotImplementedError(
                f"Action '{action}' is not supported by MeetMCPClient."
            )
