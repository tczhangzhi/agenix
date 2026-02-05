"""Write file tool."""

import os
from typing import Any, Callable, Dict, Optional

from .base import Tool, ToolResult


class WriteTool(Tool):
    """Write content to a file."""

    def __init__(self, working_dir: str = "."):
        self.working_dir = working_dir
        super().__init__(
            name="write",
            description=(
                "Write content to a file. Creates the file if it doesn't exist, overwrites if it does. "
                "Use this for new files or complete rewrites. For small changes, use edit instead."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to write (absolute or relative to working directory)"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file"
                    }
                },
                "required": ["file_path", "content"]
            }
        )

    async def execute(
        self,
        tool_call_id: str,
        arguments: Dict[str, Any],
        on_update: Optional[Callable[[str], None]] = None,
    ) -> ToolResult:
        """Execute write operation."""
        # Validate arguments
        if "file_path" not in arguments:
            return ToolResult(
                content="Error: Missing required argument 'file_path'. Please provide the path to the file you want to write.",
                is_error=True
            )

        if "content" not in arguments:
            return ToolResult(
                content="Error: Missing required argument 'content'. Please provide the content you want to write to the file.",
                is_error=True
            )

        file_path = arguments["file_path"]
        content = arguments["content"]

        # Resolve path
        if not os.path.isabs(file_path):
            file_path = os.path.join(self.working_dir, file_path)

        try:
            # Create parent directories if needed
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # Write file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            lines = len(content.split('\n'))
            return ToolResult(
                content=f"Successfully wrote {lines} lines to {file_path}",
                details={"lines": lines, "path": file_path}
            )

        except PermissionError:
            return ToolResult(
                content=f"Error: Permission denied writing to {file_path}. Check file permissions and try again.",
                is_error=True
            )
        except OSError as e:
            return ToolResult(
                content=f"Error: Unable to write file {file_path}. {str(e)}",
                is_error=True
            )
        except Exception as e:
            return ToolResult(
                content=f"Error writing file: {str(e)}. Please check the file path and try again.",
                is_error=True
            )
