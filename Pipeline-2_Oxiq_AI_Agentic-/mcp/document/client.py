from typing import Any
from shared.interfaces.tool import Tool
from mcp.document.server import DocumentMCPServer
from schemas.mcp_response import MCPResponse

class DocumentMCPClient(Tool):
    """
    Client driver connecting to the Document MCP Server.
    """
    def __init__(self):
        self.server = DocumentMCPServer()

    def execute(self, action: str, *args: Any, **kwargs: Any) -> MCPResponse:
        """
        Routes document packet compilation queries to the Document server.
        """
        workflow_id = kwargs.get("workflow_id", "")
        if action == "generate_interview_packet":
            interview_details = kwargs.get("interview_details", {})
            return self.server.generate_interview_packet(workflow_id, interview_details)
        else:
            raise NotImplementedError(
                f"Action '{action}' is not supported by DocumentMCPClient."
            )
