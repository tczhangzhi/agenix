"""Glob tool - Find files by pattern matching."""

import glob as glob_module
from pathlib import Path
from typing import Dict, Any, Optional, Callable

from .base import Tool, ToolResult


class GlobTool(Tool):
    """Glob Tool - Find files using glob patterns.

    This tool allows searching for files using wildcard patterns like:
    - *.py - All Python files in current directory
    - **/*.js - All JavaScript files recursively
    - src/**/*.test.ts - All TypeScript test files in src/
    """

    def __init__(self, working_dir: str = "."):
        """Initialize Glob Tool.

        Args:
            working_dir: Working directory for glob searches (default: current directory)
        """
        self.working_dir = Path(working_dir)

        super().__init__(
            name="glob",
            description="""Find files by pattern matching.

Use glob patterns to find files:
- *.py - Python files in current directory
- **/*.js - All JavaScript files recursively
- src/**/*.test.ts - Test files in src/
- [!.]* - Files not starting with dot

Supports standard glob syntax:
- * - matches any characters
- ** - matches directories recursively
- ? - matches single character
- [abc] - matches any of a, b, c
- [!abc] - matches any except a, b, c""",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to match files"
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory to search in (default: current directory)"
                    }
                },
                "required": ["pattern"]
            }
        )

    async def execute(
        self,
        tool_call_id: str,
        arguments: Dict[str, Any],
        on_update: Optional[Callable[[str], None]] = None,
    ) -> ToolResult:
        """Execute glob search.

        Args:
            tool_call_id: Unique ID for this tool call
            arguments: {"pattern": "*.py", "path": "optional/dir"}
            on_update: Optional progress callback

        Returns:
            ToolResult with list of matched files
        """
        pattern = arguments.get("pattern", "")
        search_path = arguments.get("path")

        if not pattern:
            return ToolResult(
                content="Error: pattern parameter is required",
                is_error=True
            )

        # Determine search directory
        if search_path:
            base = Path(search_path)
            if not base.exists():
                return ToolResult(
                    content=f"Error: Directory '{search_path}' does not exist",
                    is_error=True
                )
        else:
            base = self.working_dir

        if on_update:
            on_update(f"Searching for '{pattern}' in {base}...")

        try:
            # Execute glob search
            if "**" in pattern:
                # Recursive search
                matches = list(base.glob(pattern))
            else:
                # Non-recursive
                matches = list(base.glob(pattern))

            # Sort and format results
            matches = sorted(matches)
            relative_matches = []

            for match in matches:
                try:
                    # Try to get relative path
                    rel_path = match.relative_to(base)
                    relative_matches.append(str(rel_path))
                except ValueError:
                    # If not relative, use absolute
                    relative_matches.append(str(match))

            # Format output
            if not relative_matches:
                content = f"No files found matching pattern: {pattern}"
            else:
                count = len(relative_matches)
                files_list = "\n".join(f"  {f}" for f in relative_matches[:100])

                if len(relative_matches) > 100:
                    files_list += f"\n  ... and {len(relative_matches) - 100} more"

                content = f"""Found {count} file(s) matching '{pattern}':

{files_list}"""

            return ToolResult(
                content=content,
                details={
                    "pattern": pattern,
                    "base_dir": str(base),
                    "count": len(relative_matches),
                    "files": relative_matches
                }
            )

        except Exception as e:
            return ToolResult(
                content=f"Error during glob search: {str(e)}",
                is_error=True
            )
