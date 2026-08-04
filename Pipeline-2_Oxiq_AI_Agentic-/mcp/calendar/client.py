from typing import Any
from shared.interfaces.tool import Tool
from mcp.calendar.server import CalendarMCPServer
from schemas.mcp_response import MCPResponse

class CalendarMCPClient(Tool):
    """
    Client driver connecting to the Calendar MCP Server.
    """
    def __init__(self):
        self.server = CalendarMCPServer()

    def execute(self, action: str, *args: Any, **kwargs: Any) -> MCPResponse:
        """
        Routes calendar queries and reservation requests to the Calendar server.
        """
        workflow_id = kwargs.get("workflow_id", "")
        if action == "fetch_availability":
            interviewer_id = kwargs.get("interviewer_id", "")
            return self.server.fetch_availability(interviewer_id, workflow_id)
            
        elif action == "reserve_slot":
            slot_id = kwargs.get("slot_id", "")
            interviewer_name = kwargs.get("interviewer_name", "")
            return self.server.reserve_slot(slot_id, interviewer_name, workflow_id)
            
        else:
            raise NotImplementedError(
                f"Action '{action}' is not supported by CalendarMCPClient."
            )
