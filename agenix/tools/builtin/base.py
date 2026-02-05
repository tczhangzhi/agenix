"""Base tool interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Union

from ...core.messages import ImageContent, TextContent


@dataclass
class ToolResult:
    """Tool execution result."""
    content: Union[str, List[Union[TextContent, ImageContent]]]
    details: Optional[Dict[str, Any]] = None
    is_error: bool = False


class Tool(ABC):
    """Abstract tool interface."""

    def __init__(self, name: str, description: str, parameters: Dict[str, Any]):
        self.name = name
        self.description = description
        self.parameters = parameters

    @abstractmethod
    async def execute(
        self,
        tool_call_id: str,
        arguments: Dict[str, Any],
        on_update: Optional[Callable[[str], None]] = None,
    ) -> ToolResult:
        """Execute the tool with given arguments.

        Args:
            tool_call_id: Unique ID for this tool call
            arguments: Tool arguments (must be a dict)
            on_update: Optional callback for progress updates

        Returns:
            ToolResult with content and optional details
        """
        # Ensure arguments is a dict
        if not isinstance(arguments, dict):
            raise TypeError(
                f"Tool arguments must be a dict, got {type(arguments)}: {arguments}")
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert tool to API format."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def validate_arguments(self, arguments: Dict[str, Any]) -> None:
        """Validate tool arguments against schema."""
        required = self.parameters.get("required", [])
        for field in required:
            if field not in arguments:
                raise ValueError(f"Missing required argument: {field}")
