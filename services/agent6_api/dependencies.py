from shared.registry.tool_registry import tool_registry
from shared.config.settings import settings
from mcp.resume.client import ResumeMCPClient
from mcp.database.client import DatabaseMCPClient
from mcp.database.real_client import RealRecruitmentDBMCPClient
from mcp.calendar.client import CalendarMCPClient
from mcp.meet.client import MeetMCPClient
from mcp.document.client import DocumentMCPClient
from mcp.notification.client import NotificationMCPClient
from agents.agent6.agent import InterviewInvitationAgent

def initialize_dependencies():
    """
    Composition root function registering the required MCP client classes
    in the global ToolRegistry. Checks for prior registrations to support
    safe, idempotent execution across test runners and application launches.
    """
    # Safe register helper
    _register_if_absent("resume_mcp", ResumeMCPClient)
    
    if settings.mcp_db_mode.lower() == "real":
        # Register a lambda or class wrapper producing RealRecruitmentDBMCPClient with agent_id="agent_6"
        db_cls = lambda: RealRecruitmentDBMCPClient(agent_id="agent_6")
        _register_if_absent("database_mcp", db_cls)
    else:
        _register_if_absent("database_mcp", DatabaseMCPClient)

    _register_if_absent("calendar_mcp", CalendarMCPClient)
    _register_if_absent("meet_mcp", MeetMCPClient)
    _register_if_absent("document_mcp", DocumentMCPClient)
    _register_if_absent("notification_mcp", NotificationMCPClient)

def _register_if_absent(tool_name: str, tool_class):
    try:
        tool_registry.get_tool(tool_name)
    except KeyError:
        tool_registry.register(tool_name, tool_class)

def get_agent6() -> InterviewInvitationAgent:
    """
    FastAPI dependency injection provider returning an InterviewInvitationAgent instance.
    """
    return InterviewInvitationAgent()
