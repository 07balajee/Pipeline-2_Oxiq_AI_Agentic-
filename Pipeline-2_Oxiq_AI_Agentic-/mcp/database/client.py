from typing import Any
from shared.interfaces.tool import Tool
from mcp.database.server import DatabaseMCPServer
from schemas.mcp_response import MCPResponse

class DatabaseMCPClient(Tool):
    """
    Client driver connecting to the Database MCP Server.
    """
    def __init__(self):
        self.server = DatabaseMCPServer()

    def execute(self, action: str, *args: Any, **kwargs: Any) -> MCPResponse:
        """
        Routes database query requests to the Database server.
        """
        workflow_id = kwargs.get("workflow_id", "")
        if action == "read_candidate":
            candidate_id = kwargs.get("candidate_id", "")
            return self.server.read_candidate(candidate_id, workflow_id)
            
        elif action == "read_job":
            job_id = kwargs.get("job_id", "")
            return self.server.read_job(job_id, workflow_id)
            
        elif action == "prepare_interview":
            candidate_id = kwargs.get("candidate_id", "")
            interviewer_id = kwargs.get("interviewer_id", "")
            scheduled_time = kwargs.get("scheduled_time", "")
            return self.server.prepare_interview(candidate_id, interviewer_id, scheduled_time, workflow_id)
            
        elif action == "prepare_update":
            candidate_id = kwargs.get("candidate_id", "")
            new_state = kwargs.get("new_state", "")
            return self.server.prepare_update(candidate_id, new_state, workflow_id)
            
        elif action == "prepare_insert":
            table_name = kwargs.get("table_name", "")
            record = kwargs.get("record", {})
            return self.server.prepare_insert(table_name, record, workflow_id)
            
        elif action == "commit":
            prepared_payload = kwargs.get("prepared_payload", {})
            return self.server.commit(prepared_payload, workflow_id)
            
        elif action == "rollback":
            prepared_payload = kwargs.get("prepared_payload", {})
            return self.server.rollback(prepared_payload, workflow_id)
            
        else:
            raise NotImplementedError(
                f"Action '{action}' is not supported by DatabaseMCPClient."
            )
