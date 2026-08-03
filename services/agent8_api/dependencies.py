from shared.registry.tool_registry import tool_registry
from mcp.database.client import DatabaseMCPClient
from mcp.resume.client import ResumeMCPClient
from agents.agent8.agent import HRInterviewAgent

def initialize_dependencies():
    """
    Composition root function registering the MCP client classes required by Agent 8
    in the global ToolRegistry.
    """
    _register_if_absent("database_mcp", DatabaseMCPClient)
    _register_if_absent("resume_mcp", ResumeMCPClient)

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
