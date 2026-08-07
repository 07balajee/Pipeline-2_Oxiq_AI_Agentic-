from shared.registry.tool_registry import tool_registry
from shared.config.settings import settings
from mcp.database.client import DatabaseMCPClient
from mcp.database.real_client import RealRecruitmentDBMCPClient
from agents.agent8.agent import HRInterviewAgent

def initialize_dependencies():
    """
    Composition root function registering the MCP client classes required by Agent 8
    in the global ToolRegistry.
    """
    if settings.mcp_db_mode.lower() == "real":
        db_cls = lambda: RealRecruitmentDBMCPClient(agent_id="agent_8")
        _register_if_absent("database_mcp", db_cls)
    else:
        _register_if_absent("database_mcp", DatabaseMCPClient)

def _register_if_absent(tool_name: str, tool_class):
    try:
        tool_registry.get_tool(tool_name)
    except KeyError:
        tool_registry.register(tool_name, tool_class)

def get_agent8() -> HRInterviewAgent:
    """
    FastAPI dependency injection provider returning an HRInterviewAgent instance.
    """
    return HRInterviewAgent()
