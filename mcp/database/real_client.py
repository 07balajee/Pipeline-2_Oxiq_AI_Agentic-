import os
import sys
import json
import time
import uuid
import asyncio
import logging
from typing import Any, Dict, List, Optional
from shared.interfaces.tool import Tool
from shared.config.settings import settings
from schemas.mcp_response import MCPResponse

logger = logging.getLogger(__name__)

def _get_mcp_sdk():
    """
    Safely import official Python mcp SDK modules from site-packages,
    bypassing local workspace directory naming collisions.
    """
    import importlib.util
    import importlib

    orig_path = list(sys.path)
    cached_mcp = sys.modules.pop('mcp', None)
    try:
        # Filter out paths that contain the local workspace mcp package
        sys.path = [
            p for p in sys.path 
            if p and not os.path.exists(os.path.join(p, "mcp", "database"))
        ]
        mcp_sdk = importlib.import_module("mcp")
        stdio_module = importlib.import_module("mcp.client.stdio")
        session_module = importlib.import_module("mcp.client.session")
        return mcp_sdk, stdio_module, session_module
    finally:
        sys.path = orig_path
        if cached_mcp is not None:
            sys.modules['mcp'] = cached_mcp

class RealRecruitmentDBMCPClient(Tool):
    """
    Compatibility Client Adapter connecting Pipeline-2 workers to the real
    Recruitment Database MCP Server (mcp_server_extracted/MCP_recruitementDB_Server/server.py).
    
    Translates Pipeline-2's typed database operations (read_candidate, read_job,
    prepare_interview, prepare_update, prepare_insert, commit, rollback) into
    FastMCP tool calls (query_resource, write_resource, transition_status).
    """

    def __init__(self, agent_id: str = "agent_6", server_path: Optional[str] = None, transport: Optional[str] = None):
        self.agent_id = agent_id
        self.server_path = server_path or settings.mcp_db_server_path
        self.transport = transport or settings.mcp_db_transport
        self.http_url = settings.mcp_db_http_url
        self._prepared_descriptors: List[Dict[str, Any]] = []

    async def _call_mcp_tool_async(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        Executes a single tool call on the Recruitment DB MCP server using stdio transport.
        """
        mcp_sdk, stdio_module, session_module = _get_mcp_sdk()
        ClientSession = session_module.ClientSession
        StdioServerParameters = stdio_module.StdioServerParameters
        stdio_client = stdio_module.stdio_client

        abs_server = os.path.abspath(self.server_path)
        server_dir = os.path.dirname(abs_server)
        
        # Inherit current env and ensure PYTHONPATH for server subprocess does not include local mcp package
        env = {**os.environ}
        if "PYTHONPATH" in env:
            paths = env["PYTHONPATH"].split(os.pathsep)
            clean_paths = [
                p for p in paths 
                if not (p and os.path.exists(os.path.join(p, "mcp", "database")))
            ]
            env["PYTHONPATH"] = os.pathsep.join(clean_paths)

        server_params = StdioServerParameters(
            command=sys.executable,
            args=[abs_server],
            env=env
        )

        args = {"agent_id": self.agent_id, **kwargs}

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, args)
                
                # Check for structured content return
                if getattr(result, "structuredContent", None):
                    sc = result.structuredContent
                    return sc.get("result", sc) if isinstance(sc, dict) else sc
                
                for block in getattr(result, "content", []):
                    text = getattr(block, "text", None)
                    if text:
                        try:
                            return json.loads(text)
                        except json.JSONDecodeError:
                            return {"raw": text}
                return {"ok": False, "code": "empty_response", "message": "No content returned from MCP tool."}

    def _call_mcp_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        Synchronous bridge to call async MCP stdio tool.
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            # If running inside an existing event loop (e.g. FastAPI / pytest-asyncio)
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(self._call_mcp_tool_async(tool_name, **kwargs))
        else:
            return loop.run_until_complete(self._call_mcp_tool_async(tool_name, **kwargs))

    def execute(self, action: str, *args: Any, **kwargs: Any) -> MCPResponse:
        """
        Routes pipeline database query requests to corresponding FastMCP tools on the server.
        """
        start_time = time.time()
        workflow_id = kwargs.get("workflow_id", "")
        trace_id = str(uuid.uuid4())
        caller_agent = kwargs.get("agent_id", self.agent_id)
        
        # Override invoking agent ID if passed in kwargs
        saved_agent = self.agent_id
        self.agent_id = caller_agent

        try:
            if action == "read_candidate":
                candidate_id = kwargs.get("candidate_id", "")
                res = self._call_mcp_tool("query_resource", table="candidates", filters={"id": candidate_id})
                
                if not res.get("ok"):
                    code = res.get("code", "query_failed")
                    msg = res.get("message", "Candidate lookup failed.")
                    return MCPResponse(
                        status="FAILED",
                        mcp_name="RealRecruitmentDBMCP",
                        workflow_id=workflow_id,
                        trace_id=trace_id,
                        execution_time_ms=(time.time() - start_time) * 1000,
                        errors=[f"[{code}] {msg}"],
                        metadata={"code": code, "raw": res}
                    )
                
                rows = res.get("rows", [])
                if not rows:
                    return MCPResponse(
                        status="FAILED",
                        mcp_name="RealRecruitmentDBMCP",
                        workflow_id=workflow_id,
                        trace_id=trace_id,
                        execution_time_ms=(time.time() - start_time) * 1000,
                        errors=[f"Candidate ID '{candidate_id}' not found in database."],
                        metadata={"code": "record_not_found"}
                    )
                
                cand_row = rows[0]
                # Format payload to match Pipeline-2 Candidate Schema
                payload = {
                    "candidate_id": str(cand_row.get("id", candidate_id)),
                    "name": cand_row.get("name", "Unknown"),
                    "email": cand_row.get("email", ""),
                    "resume_url": cand_row.get("resume_url", ""),
                    "job_id": str(cand_row.get("job_id", "")),
                    "pipeline_state": cand_row.get("status", "Applied"),
                    "screening_score": cand_row.get("screening_score", 85.0)
                }

                metadata = {
                    "source": res.get("source", "database"),
                    "stale": res.get("stale", False)
                }
                if res.get("stale"):
                    metadata["warning"] = "Data returned from legacy JSON twin; database is offline or empty."

                return MCPResponse(
                    status="SUCCESS",
                    mcp_name="RealRecruitmentDBMCP",
                    workflow_id=workflow_id,
                    trace_id=trace_id,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    payload=payload,
                    metadata=metadata
                )

            elif action == "read_job":
                job_id = kwargs.get("job_id", "")
                res = self._call_mcp_tool("query_resource", table="jobs", filters={"id": job_id})
                
                if not res.get("ok"):
                    code = res.get("code", "query_failed")
                    msg = res.get("message", "Job lookup failed.")
                    return MCPResponse(
                        status="FAILED",
                        mcp_name="RealRecruitmentDBMCP",
                        workflow_id=workflow_id,
                        trace_id=trace_id,
                        execution_time_ms=(time.time() - start_time) * 1000,
                        errors=[f"[{code}] {msg}"],
                        metadata={"code": code, "raw": res}
                    )

                rows = res.get("rows", [])
                if not rows:
                    return MCPResponse(
                        status="FAILED",
                        mcp_name="RealRecruitmentDBMCP",
                        workflow_id=workflow_id,
                        trace_id=trace_id,
                        execution_time_ms=(time.time() - start_time) * 1000,
                        errors=[f"Job ID '{job_id}' not found in database."],
                        metadata={"code": "record_not_found"}
                    )

                job_row = rows[0]
                payload = {
                    "job_id": str(job_row.get("id", job_id)),
                    "job_title": job_row.get("title", "Software Engineer"),
                    "department": job_row.get("department", "Engineering"),
                    "technical_criteria": job_row.get("technical_criteria", ["Python", "Transformers", "Pydantic"]),
                    "soft_skills_criteria": job_row.get("soft_skills_criteria", ["Communication", "Culture Fit"]),
                    "status": job_row.get("status", "ACTIVE")
                }

                metadata = {
                    "source": res.get("source", "database"),
                    "stale": res.get("stale", False)
                }

                return MCPResponse(
                    status="SUCCESS",
                    mcp_name="RealRecruitmentDBMCP",
                    workflow_id=workflow_id,
                    trace_id=trace_id,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    payload=payload,
                    metadata=metadata
                )

            elif action == "prepare_interview":
                candidate_id = kwargs.get("candidate_id", "")
                interviewer_id = kwargs.get("interviewer_id", "")
                scheduled_time = kwargs.get("scheduled_time", "")
                
                descriptor = {
                    "type": "interview_insert",
                    "candidate_id": candidate_id,
                    "interviewer": interviewer_id,
                    "scheduled_at": scheduled_time,
                    "status": "Scheduled"
                }
                self._prepared_descriptors.append(descriptor)
                
                return MCPResponse(
                    status="SUCCESS",
                    mcp_name="RealRecruitmentDBMCP",
                    workflow_id=workflow_id,
                    trace_id=trace_id,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    payload={"prepared_action": "INSERT_INTERVIEW", "data": descriptor}
                )

            elif action == "prepare_update":
                candidate_id = kwargs.get("candidate_id", "")
                new_state = kwargs.get("new_state", "")
                
                descriptor = {
                    "type": "candidate_transition",
                    "candidate_id": candidate_id,
                    "to_status": new_state
                }
                self._prepared_descriptors.append(descriptor)
                
                return MCPResponse(
                    status="SUCCESS",
                    mcp_name="RealRecruitmentDBMCP",
                    workflow_id=workflow_id,
                    trace_id=trace_id,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    payload={"prepared_action": "UPDATE_CANDIDATE_STATE", "data": descriptor}
                )

            elif action == "prepare_insert":
                table_name = kwargs.get("table_name", "")
                record = kwargs.get("record", {})
                
                descriptor = {
                    "type": "table_insert",
                    "table_name": table_name,
                    "record": record
                }
                self._prepared_descriptors.append(descriptor)
                
                return MCPResponse(
                    status="SUCCESS",
                    mcp_name="RealRecruitmentDBMCP",
                    workflow_id=workflow_id,
                    trace_id=trace_id,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    payload={"prepared_action": f"INSERT_{table_name.upper()}", "data": record}
                )

            elif action == "commit":
                if not self._prepared_descriptors:
                    prepared_payload = kwargs.get("prepared_payload", {})
                    if prepared_payload and isinstance(prepared_payload, dict):
                        data = prepared_payload.get("data", {})
                        if data and isinstance(data, dict) and "type" in data:
                            self._prepared_descriptors.append(data)

                if not self._prepared_descriptors:
                    return MCPResponse(
                        status="SUCCESS",
                        mcp_name="RealRecruitmentDBMCP",
                        workflow_id=workflow_id,
                        trace_id=trace_id,
                        execution_time_ms=(time.time() - start_time) * 1000,
                        message="No prepared descriptors to commit.",
                        payload={"committed": True, "executed_steps": 0}
                    )

                succeeded_steps = []
                failed_steps = []
                
                for desc in list(self._prepared_descriptors):
                    desc_type = desc.get("type")
                    if desc_type == "interview_insert":
                        # Execute write_resource on interviews table
                        res = self._call_mcp_tool(
                            "write_resource",
                            table="interviews",
                            op="insert",
                            data={
                                "candidate_id": desc.get("candidate_id"),
                                "candidate_name": f"Candidate-{desc.get('candidate_id')}",
                                "interviewer": desc.get("interviewer"),
                                "scheduled_at": desc.get("scheduled_at"),
                                "status": desc.get("status", "Scheduled")
                            }
                        )
                        if res.get("ok"):
                            succeeded_steps.append({"step": "interview_insert", "res": res})
                        else:
                            failed_steps.append({"step": "interview_insert", "error": res})

                    elif desc_type == "candidate_transition":
                        # Execute transition_status on candidates entity
                        res = self._call_mcp_tool(
                            "transition_status",
                            entity="candidates",
                            entity_id=desc.get("candidate_id"),
                            to_status=desc.get("to_status", "Interview"),
                            reason="Pipeline-2 Agent 6 scheduling event transition"
                        )
                        if res.get("ok"):
                            succeeded_steps.append({"step": "candidate_transition", "res": res})
                        else:
                            failed_steps.append({"step": "candidate_transition", "error": res})

                    elif desc_type == "table_insert":
                        res = self._call_mcp_tool(
                            "write_resource",
                            table=desc.get("table_name"),
                            op="insert",
                            data=desc.get("record", {})
                        )
                        if res.get("ok"):
                            succeeded_steps.append({"step": "table_insert", "res": res})
                        else:
                            failed_steps.append({"step": "table_insert", "error": res})

                # Clear prepared queue after attempt
                self._prepared_descriptors.clear()

                if failed_steps:
                    return MCPResponse(
                        status="FAILED",
                        mcp_name="RealRecruitmentDBMCP",
                        workflow_id=workflow_id,
                        trace_id=trace_id,
                        execution_time_ms=(time.time() - start_time) * 1000,
                        errors=[f"Commit failed on step '{f['step']}': {f['error'].get('message')}" for f in failed_steps],
                        metadata={
                            "code": failed_steps[0]["error"].get("code", "commit_failed"),
                            "succeeded_steps": len(succeeded_steps),
                            "failed_steps": len(failed_steps),
                            "partial_execution": True
                        }
                    )

                return MCPResponse(
                    status="SUCCESS",
                    mcp_name="RealRecruitmentDBMCP",
                    workflow_id=workflow_id,
                    trace_id=trace_id,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    message="All prepared database operations successfully executed on live MCP server.",
                    payload={"committed": True, "executed_steps": len(succeeded_steps)}
                )

            elif action == "rollback":
                count = len(self._prepared_descriptors)
                self._prepared_descriptors.clear()
                return MCPResponse(
                    status="SUCCESS",
                    mcp_name="RealRecruitmentDBMCP",
                    workflow_id=workflow_id,
                    trace_id=trace_id,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    message="Database transaction prepared operations discarded.",
                    payload={"rolled_back": True, "discarded_steps": count}
                )

            else:
                raise NotImplementedError(f"Action '{action}' is not supported by RealRecruitmentDBMCPClient.")

        except Exception as e:
            logger.exception("RealRecruitmentDBMCPClient execution error")
            return MCPResponse(
                status="FAILED",
                mcp_name="RealRecruitmentDBMCP",
                workflow_id=workflow_id,
                trace_id=trace_id,
                execution_time_ms=(time.time() - start_time) * 1000,
                errors=[f"MCP Client adapter error: {str(e)}"],
                metadata={"code": "adapter_error"}
            )
        finally:
            self.agent_id = saved_agent

    def validate_capabilities(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Validates MCP capabilities for the invoking agent by calling list_capabilities.
        """
        target_agent = agent_id or self.agent_id
        return self._call_mcp_tool("list_capabilities", agent_id=target_agent)
