from abc import ABC, abstractmethod
from typing import Any

class Tool(ABC):
    """
    Abstract Base Class for all system integration tools and Model Context Protocol (MCP) clients.
    Guarantees a standard tool execution interface (execute).
    """

    @abstractmethod
    def execute(self, *args: Any, **kwargs: Any) -> Any:
        """
        Executes the utility integration tool task (e.g., email notification, db write, calendar slot check).
        
        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
            
        Returns:
            Any: The outcome of the tool execution.
        """
        pass
