from agents.master.master_agent import MasterAgent

_master_agent_instance = None

def get_master_agent() -> MasterAgent:
    """
    Dependency provider returning the process-scoped MasterAgent singleton.
    Guarantees thread checkpoints and timeline/context data persist between requests.
    """
    global _master_agent_instance
    if _master_agent_instance is None:
        _master_agent_instance = MasterAgent()
    return _master_agent_instance
