"""Action and Tool Registry for Astra AI Core discovery.

Provides tool discovery, metadata inspection, and invoker functions.
To be fully populated in Milestone 7.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional
from actions.base import ActionResult


@dataclass
class ToolMetadata:
    """Metadata describing an action tool for AI discovery and planning."""
    name: str
    description: str
    parameters: Dict[str, Any]
    function: Callable[..., ActionResult]
    requires_confirmation: bool = False
    category: str = "general"

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary excluding the callable function."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "requires_confirmation": self.requires_confirmation,
            "category": self.category,
        }


class ActionRegistry:
    """Registry maintaining all available tools for Astra AI Core."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolMetadata] = {}

    def register(self, tool: ToolMetadata) -> None:
        """Register a new action tool."""
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[ToolMetadata]:
        """Retrieve tool metadata by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        """List all tool descriptions for AI schema generation."""
        return [tool.to_dict() for tool in self._tools.values()]

    def execute(self, name: str, **kwargs: Any) -> ActionResult:
        """Execute a registered tool by name with arguments."""
        tool = self._tools.get(name)
        if not tool:
            return ActionResult.fail(f"Tool '{name}' is not registered.")
        try:
            return tool.function(**kwargs)
        except Exception as exc:
            return ActionResult.fail(
                f"Error executing tool '{name}': {exc}", error=str(exc)
            )


# Default global registry instance
registry = ActionRegistry()
