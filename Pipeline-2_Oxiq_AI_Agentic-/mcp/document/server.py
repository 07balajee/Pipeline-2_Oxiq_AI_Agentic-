import time
import uuid
from typing import Any, Dict
from mcp.document.mock import get_mock_document_packet
from schemas.mcp_response import MCPResponse

class DocumentMCPServer:
    """
    Mock Document MCP Server simulating report and packet compilation.
    """

    def generate_interview_packet(self, workflow_id: str, interview_details: Dict[str, Any]) -> MCPResponse:
        start_time = time.time()
        time.sleep(0.04)
        trace_id = str(uuid.uuid4())
        payload = get_mock_document_packet(workflow_id)
        
        return MCPResponse(
            status="SUCCESS",
            mcp_name="DocumentMCP",
            workflow_id=workflow_id,
            trace_id=trace_id,
            execution_time_ms=(time.time() - start_time) * 1000,
            payload=payload,
            metadata={"interview_mode": interview_details.get("interview_mode")}
        )
