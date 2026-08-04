import time
import uuid
from mcp.resume.mock import get_mock_resume_data
from schemas.mcp_response import MCPResponse

class ResumeMCPServer:
    """
    Mock Resume MCP Server implementing candidate profile extraction logic.
    """
    def get_resume_summary(self, workflow_id: str, resume_url: str) -> MCPResponse:
        start_time = time.time()
        time.sleep(0.04)  # Simulate server parsing latency
        trace_id = str(uuid.uuid4())
        payload = get_mock_resume_data(workflow_id)
        
        return MCPResponse(
            status="SUCCESS",
            mcp_name="ResumeMCP",
            workflow_id=workflow_id,
            trace_id=trace_id,
            execution_time_ms=(time.time() - start_time) * 1000,
            payload=payload,
            warnings=[],
            errors=[],
            metadata={"processed_url": resume_url}
        )
