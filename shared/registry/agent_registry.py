from typing import Dict, Type
from shared.interfaces.agent import Agent
from shared.logger.logger import workflow_logger

class AgentRegistry:
    """
    Registry management class to index and resolve agent classes dynamically
    without hardcoding imports or direct class references in the orchestrator.
    """
    def __init__(self):
        self._agents: Dict[str, Type[Agent]] = {}

    def register(self, agent_name: str, agent_class: Type[Agent]):
        """
        Registers an agent class to a unique name/key.
        """
        self._agents[agent_name] = agent_class
        workflow_logger.info(f"Registered agent: {agent_name} -> {agent_class.__name__}")

    def get_agent(self, agent_name: str) -> Type[Agent]:
        """
        Resolves and returns the agent class matching the given name key.
        """
        if agent_name not in self._agents:
            raise KeyError(f"Agent '{agent_name}' is not registered in the AgentRegistry.")
        return self._agents[agent_name]

# Global agent registry instance
agent_registry = AgentRegistry()
