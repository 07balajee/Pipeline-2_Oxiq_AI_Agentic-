from typing import Any, Dict
from shared.registry.tool_registry import tool_registry
from schemas.mcp_response import MCPResponse


class Agent8ToolsAdapter:
    """
    Thin adapter class mapping HR evaluation & ranking helper invocations to
    corresponding MCP Client instances resolved dynamically from the
    ToolRegistry. Mirrors agents/agent6/tools.py's pattern so every agent in
    the pipeline resolves its MCPs the same way.
    """

    @staticmethod
    def read_candidate(candidate_id: str, workflow_id: str, metadata: Dict[str, Any] = None) -> MCPResponse:
        client_cls = tool_registry.get_tool("database_mcp")
        return client_cls().execute(
            action="read_candidate",
            candidate_id=candidate_id,
            workflow_id=workflow_id,
            metadata=metadata
        )

    @staticmethod
    def read_job(job_id: str, workflow_id: str, metadata: Dict[str, Any] = None) -> MCPResponse:
        client_cls = tool_registry.get_tool("database_mcp")
        return client_cls().execute(
            action="read_job",
            job_id=job_id,
            workflow_id=workflow_id,
            metadata=metadata
        )

    @staticmethod
    def commit_hr_results(payload: Dict[str, Any], workflow_id: str, metadata: Dict[str, Any] = None) -> MCPResponse:
        client_cls = tool_registry.get_tool("database_mcp")
        return client_cls().execute(
            action="commit",
            prepared_payload=payload,
            workflow_id=workflow_id,
            metadata=metadata
        )
