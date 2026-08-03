from shared.registry.tool_registry import tool_registry
from shared.config.settings import settings
from mcp.database.client import DatabaseMCPClient
from mcp.database.real_client import RealRecruitmentDBMCPClient
from mcp.resume.client import ResumeMCPClient
from agents.agent7.agent import TechnicalInterviewAgent

def initialize_dependencies():
    """
    Composition root function registering the MCP client classes required by Agent 7
    in the global ToolRegistry.
    """
    if settings.mcp_db_mode.lower() == "real":
        db_cls = lambda: RealRecruitmentDBMCPClient(agent_id="agent_7")
        _register_if_absent("database_mcp", db_cls)
    else:
        _register_if_absent("database_mcp", DatabaseMCPClient)
    _register_if_absent("resume_mcp", ResumeMCPClient)

def _register_if_absent(tool_name: str, tool_class):
    try:
        tool_registry.get_tool(tool_name)
    except KeyError:
        tool_registry.register(tool_name, tool_class)

def get_agent7() -> TechnicalInterviewAgent:
    """
    FastAPI dependency injection provider returning a TechnicalInterviewAgent instance.
    """
    return TechnicalInterviewAgent()
