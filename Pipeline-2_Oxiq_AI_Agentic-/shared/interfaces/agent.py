from abc import ABC, abstractmethod
from schemas.agent_response import AgentResponse
from shared.context.workflow_context import WorkflowContext

class Agent(ABC):
    """
    Abstract Base Class for all specialized agents (workers) in the recruitment pipeline.
    Ensures a consistent interface (run) and standard return type (AgentResponse).
    """

    @abstractmethod
    def run(self, context: WorkflowContext) -> AgentResponse:
        """
        Executes the agent's specific business duty under the given context.
        
        Args:
            context (WorkflowContext): The isolated candidate and execution context parameters.
            
        Returns:
            AgentResponse: Standardized return model containing execution status and outputs.
        """
        pass
