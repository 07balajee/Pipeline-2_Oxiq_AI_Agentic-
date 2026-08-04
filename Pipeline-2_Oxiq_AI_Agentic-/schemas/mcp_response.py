from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class MCPResponse(BaseModel):
    """
    Standardized response envelope returned by all Model Context Protocol (MCP) clients and servers.
    Ensures unified schema telemetry logs matching enterprise tracing requirements.
    """
    status: str = Field(..., description="Response status: SUCCESS or FAILED")
    mcp_name: str = Field(..., description="Name of the executing MCP Server")
    workflow_id: str = Field(..., description="Active Candidate Workflow Run UUID")
    trace_id: str = Field(..., description="Transaction execution context trace ID")
    execution_time_ms: float = Field(..., description="Server execution latency in milliseconds")
    payload: Any = Field(default=None, description="Actual return details/payload model")
    warnings: List[str] = Field(default_factory=list, description="Warnings generated during step run")
    errors: List[str] = Field(default_factory=list, description="Error messages list if execution failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata dictionary tracking details")
