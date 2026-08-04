from typing import Dict, Type
from shared.interfaces.tool import Tool
from shared.logger.logger import workflow_logger

class ToolRegistry:
    """
    Registry management class to index and resolve tool classes dynamically
    without hardcoding tool client calls inside agent wrappers.
    """
    def __init__(self):
        self._tools: Dict[str, Type[Tool]] = {}

    def register(self, tool_name: str, tool_class: Type[Tool]):
        """
        Registers a tool class to a unique configuration key.
        """
        self._tools[tool_name] = tool_class
        workflow_logger.info(f"Registered tool: {tool_name} -> {tool_class.__name__}")

    def get_tool(self, tool_name: str) -> Type[Tool]:
        """
        Resolves and returns the tool class matching the given key.
        """
        if tool_name not in self._tools:
            raise KeyError(f"Tool '{tool_name}' is not registered in the ToolRegistry.")
        return self._tools[tool_name]

# Global tool registry instance
tool_registry = ToolRegistry()
