"""Read file tool."""

import base64
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from ...core.messages import ImageContent, TextContent
from .base import Tool, ToolResult


class ReadTool(Tool):
    """Read file content with image support."""

    def __init__(self, working_dir: str = "."):
        self.working_dir = working_dir
        super().__init__(
            name="read",
            description=(
                "Read the contents of a file. Supports text files and images (jpg, png, gif, webp). "
                "Images are sent as attachments. For large text files, output may be truncated - "
                "use offset/limit parameters to read in chunks. When you need the full file, "
                "continue with offset until complete."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to read (absolute or relative to working directory)"
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Starting line number (1-indexed). Optional, for reading large files in chunks.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of lines to read. Optional, for reading large files in chunks.",
                    }
                },
                "required": ["file_path"]
            }
        )

    async def execute(
        self,
        tool_call_id: str,
        arguments: Dict[str, Any],
        on_update: Optional[Callable[[str], None]] = None,
    ) -> ToolResult:
        """Execute read operation."""
        file_path = arguments["file_path"]
        offset = arguments.get("offset", 1)
        limit = arguments.get("limit")

        # Resolve path
        if not os.path.isabs(file_path):
            file_path = os.path.join(self.working_dir, file_path)

        try:
            # Check if file exists
            if not os.path.exists(file_path):
                return ToolResult(
                    content=f"Error: File not found: {file_path}",
                    is_error=True
                )

            # Check if it's an image
            ext = Path(file_path).suffix.lower()
            if ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
                return await self._read_image(file_path)

            # Read text file
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            total_lines = len(lines)

            # Apply offset and limit
            start_idx = max(0, offset - 1)
            end_idx = start_idx + limit if limit else len(lines)
            selected_lines = lines[start_idx:end_idx]

            # Format with line numbers
            formatted_lines = []
            for i, line in enumerate(selected_lines, start=start_idx + 1):
                formatted_lines.append(f"{i:6d}\t{line.rstrip()}")

            content = "\n".join(formatted_lines)

            # Add truncation info
            details = {}
            if offset > 1 or (limit and end_idx < total_lines):
                truncation_msg = f"\n\n[Showing lines {start_idx + 1}-{end_idx} of {total_lines} total lines]"
                content += truncation_msg
                details["truncated"] = True
                details["total_lines"] = total_lines
                details["shown_lines"] = len(selected_lines)

            return ToolResult(content=content, details=details)

        except PermissionError:
            return ToolResult(
                content=f"Error: Permission denied: {file_path}",
                is_error=True
            )
        except UnicodeDecodeError:
            return ToolResult(
                content=f"Error: File is not a text file or uses unsupported encoding: {file_path}",
                is_error=True
            )
        except Exception as e:
            return ToolResult(
                content=f"Error reading file: {str(e)}",
                is_error=True
            )

    async def _read_image(self, file_path: str) -> ToolResult:
        """Read image file and return as base64."""
        try:
            with open(file_path, 'rb') as f:
                image_data = f.read()

            # Get MIME type
            ext = Path(file_path).suffix.lower()
            mime_map = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.webp': 'image/webp',
            }
            media_type = mime_map.get(ext, 'image/png')

            # Encode as base64
            encoded = base64.b64encode(image_data).decode('utf-8')

            # Return as image content
            image_content = ImageContent(
                source={
                    "type": "base64",
                    "media_type": media_type,
                    "data": encoded
                }
            )

            return ToolResult(
                content=[
                    TextContent(
                        text=f"[Image: {os.path.basename(file_path)}]"),
                    image_content
                ]
            )

        except Exception as e:
            return ToolResult(
                content=f"Error reading image: {str(e)}",
                is_error=True
            )
