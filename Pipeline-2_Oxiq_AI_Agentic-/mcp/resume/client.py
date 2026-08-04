from typing import Any
from shared.interfaces.tool import Tool
from mcp.resume.server import ResumeMCPServer
from schemas.mcp_response import MCPResponse

class ResumeMCPClient(Tool):
    """
    Client driver connecting to the Resume MCP Server.
    Inherits from the standard shared Tool class.
    """
    def __init__(self):
        self.server = ResumeMCPServer()

    def execute(self, action: str, *args: Any, **kwargs: Any) -> MCPResponse:
        """
        Routes the tool request to the server action.
        """
        workflow_id = kwargs.get("workflow_id", "")
        if action == "get_resume_summary":
            resume_url = kwargs.get("resume_url", "")
            return self.server.get_resume_summary(workflow_id, resume_url)
        else:
            raise NotImplementedError(
                f"Action '{action}' is not supported by ResumeMCPClient."
            )
