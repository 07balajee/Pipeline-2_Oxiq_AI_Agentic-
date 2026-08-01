import time
import uuid
from typing import Any, Dict
from mcp.database.mock import get_mock_candidate_records
from schemas.mcp_response import MCPResponse

class DatabaseMCPServer:
    """
    Mock Database MCP Server simulating isolated reading, preparation, and commits.
    """

    def read_candidate(self, candidate_id: str, workflow_id: str) -> MCPResponse:
        start_time = time.time()
        time.sleep(0.03)  # Simulate DB read latency
        trace_id = str(uuid.uuid4())
        payload = get_mock_candidate_records(candidate_id)
        
        return MCPResponse(
            status="SUCCESS",
            mcp_name="DatabaseMCP",
            workflow_id=workflow_id,
            trace_id=trace_id,
            execution_time_ms=(time.time() - start_time) * 1000,
            payload=payload
        )

    def read_job(self, job_id: str, workflow_id: str) -> MCPResponse:
        start_time = time.time()
        time.sleep(0.02)
        trace_id = str(uuid.uuid4())
        
        # Mock database lookup for jobs
        mock_jobs = {
            "job-abc-123": {
                "job_id": "job-abc-123",
                "job_title": "AI Engineer",
                "department": "Engineering",
                "technical_criteria": ["Python", "Transformers", "Pydantic"],
                "soft_skills_criteria": ["Communication", "Culture Fit", "Leadership"],
                "status": "ACTIVE"
            },
            "job-xyz-456": {
                "job_id": "job-xyz-456",
                "job_title": "Software Engineer",
                "department": "Engineering",
                "technical_criteria": ["Python", "React", "TypeScript"],
                "soft_skills_criteria": ["Communication", "Collaboration"],
                "status": "ACTIVE"
            },
            "job-inactive-789": {
                "job_id": "job-inactive-789",
                "job_title": "Product Manager",
                "department": "Product",
                "technical_criteria": ["Agile", "SQL"],
                "soft_skills_criteria": ["Leadership"],
                "status": "INACTIVE"
            }
        }
        
        payload = mock_jobs.get(job_id)
        if not payload:
            return MCPResponse(
                status="FAILED",
                mcp_name="DatabaseMCP",
                workflow_id=workflow_id,
                trace_id=trace_id,
                execution_time_ms=(time.time() - start_time) * 1000,
                errors=[f"Job ID '{job_id}' not found in database."]
            )
            
        return MCPResponse(
            status="SUCCESS",
            mcp_name="DatabaseMCP",
            workflow_id=workflow_id,
            trace_id=trace_id,
            execution_time_ms=(time.time() - start_time) * 1000,
            payload=payload
        )

    def prepare_interview(self, candidate_id: str, interviewer_id: str, scheduled_time: str, workflow_id: str) -> MCPResponse:
        start_time = time.time()
        time.sleep(0.02)
        trace_id = str(uuid.uuid4())
        payload = {
            "candidate_id": candidate_id,
            "interviewer_id": interviewer_id,
            "scheduled_time": scheduled_time,
            "status": "PENDING"
        }
        return MCPResponse(
            status="SUCCESS",
            mcp_name="DatabaseMCP",
            workflow_id=workflow_id,
            trace_id=trace_id,
            execution_time_ms=(time.time() - start_time) * 1000,
            payload={"prepared_action": "INSERT_INTERVIEW", "data": payload}
        )

    def prepare_update(self, candidate_id: str, new_state: str, workflow_id: str) -> MCPResponse:
        start_time = time.time()
        time.sleep(0.02)
        trace_id = str(uuid.uuid4())
        payload = {
            "candidate_id": candidate_id,
            "new_state": new_state
        }
        return MCPResponse(
            status="SUCCESS",
            mcp_name="DatabaseMCP",
            workflow_id=workflow_id,
            trace_id=trace_id,
            execution_time_ms=(time.time() - start_time) * 1000,
            payload={"prepared_action": "UPDATE_CANDIDATE_STATE", "data": payload}
        )

    def prepare_insert(self, table_name: str, record: Dict[str, Any], workflow_id: str) -> MCPResponse:
        start_time = time.time()
        time.sleep(0.02)
        trace_id = str(uuid.uuid4())
        return MCPResponse(
            status="SUCCESS",
            mcp_name="DatabaseMCP",
            workflow_id=workflow_id,
            trace_id=trace_id,
            execution_time_ms=(time.time() - start_time) * 1000,
            payload={"prepared_action": f"INSERT_{table_name.upper()}", "data": record}
        )

    def commit(self, prepared_payload: Dict[str, Any], workflow_id: str) -> MCPResponse:
        start_time = time.time()
        time.sleep(0.05)  # Simulate commit writing execution time
        trace_id = str(uuid.uuid4())
        return MCPResponse(
            status="SUCCESS",
            mcp_name="DatabaseMCP",
            workflow_id=workflow_id,
            trace_id=trace_id,
            execution_time_ms=(time.time() - start_time) * 1000,
            message="Database transaction successfully committed.",
            payload={"committed": True, "action": prepared_payload.get("prepared_action")}
        )

    def rollback(self, prepared_payload: Dict[str, Any], workflow_id: str) -> MCPResponse:
        start_time = time.time()
        time.sleep(0.01)
        trace_id = str(uuid.uuid4())
        return MCPResponse(
            status="SUCCESS",
            mcp_name="DatabaseMCP",
            workflow_id=workflow_id,
            trace_id=trace_id,
            execution_time_ms=(time.time() - start_time) * 1000,
            message="Database transaction successfully rolled back.",
            payload={"rolled_back": True}
        )
