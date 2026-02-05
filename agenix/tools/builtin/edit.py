"""Edit file tool with exact string replacement."""

import difflib
import os
from typing import Any, Callable, Dict, Optional

from .base import Tool, ToolResult


class EditTool(Tool):
    """Edit file by replacing exact strings."""

    def __init__(self, working_dir: str = "."):
        self.working_dir = working_dir
        super().__init__(
            name="edit",
            description=(
                "Edit a file by replacing exact text. The old_string must match exactly "
                "(including whitespace). Use this for precise, surgical edits. For multiple "
                "changes, make separate edit calls. If unsure of exact text, use read first."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to edit"
                    },
                    "old_string": {
                        "type": "string",
                        "description": "Exact string to replace (must match exactly including whitespace)"
                    },
                    "new_string": {
                        "type": "string",
                        "description": "New string to replace with"
                    },
                    "replace_all": {
                        "type": "boolean",
                        "description": "Replace all occurrences (default: false, only first occurrence)",
                        "default": False
                    }
                },
                "required": ["file_path", "old_string", "new_string"]
            }
        )

    async def execute(
        self,
        tool_call_id: str,
        arguments: Dict[str, Any],
        on_update: Optional[Callable[[str], None]] = None,
    ) -> ToolResult:
        """Execute edit operation."""
        # Validate arguments
        if "file_path" not in arguments:
            return ToolResult(
                content="Error: Missing required argument 'file_path'. Please provide the path to the file you want to edit.",
                is_error=True
            )

        if "old_string" not in arguments:
            return ToolResult(
                content="Error: Missing required argument 'old_string'. Please provide the exact text you want to replace.",
                is_error=True
            )

        if "new_string" not in arguments:
            return ToolResult(
                content="Error: Missing required argument 'new_string'. Please provide the new text to replace with.",
                is_error=True
            )

        file_path = arguments["file_path"]
        old_string = arguments["old_string"]
        new_string = arguments["new_string"]
        replace_all = arguments.get("replace_all", False)

        # Resolve path
        if not os.path.isabs(file_path):
            file_path = os.path.join(self.working_dir, file_path)

        try:
            # Read file
            if not os.path.exists(file_path):
                return ToolResult(
                    content=f"Error: File not found: {file_path}. Please check the path and ensure the file exists.",
                    is_error=True
                )

            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()

            # Check if old_string exists
            if old_string not in original_content:
                # Try to provide helpful feedback
                similar = self._find_similar_strings(
                    original_content, old_string)
                msg = f"Error: Could not find the exact text to replace in {file_path}.\n"
                msg += "The old_string must match exactly (including whitespace).\n"
                msg += "Tip: Use the read tool first to see the exact content."
                if similar:
                    msg += f"\n\nDid you mean one of these?\n{similar}"
                return ToolResult(content=msg, is_error=True)

            # Perform replacement
            if replace_all:
                new_content = original_content.replace(old_string, new_string)
                count = original_content.count(old_string)
            else:
                new_content = original_content.replace(
                    old_string, new_string, 1)
                count = 1

            # Write back
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            # Generate diff
            diff = self._generate_diff(
                original_content, new_content, file_path)

            # Find first changed line
            first_changed_line = self._find_first_changed_line(
                original_content, new_content)

            result_msg = f"Successfully replaced {count} occurrence(s) in {file_path}"
            if first_changed_line:
                result_msg += f" (first change at line {first_changed_line})"

            return ToolResult(
                content=f"{result_msg}\n\n{diff}",
                details={
                    "diff": diff,
                    "first_changed_line": first_changed_line,
                    "replacements": count
                }
            )

        except PermissionError:
            return ToolResult(
                content=f"Error: Permission denied editing {file_path}. Check file permissions.",
                is_error=True
            )
        except UnicodeDecodeError:
            return ToolResult(
                content=f"Error: Unable to read {file_path}. File might be binary or use unsupported encoding.",
                is_error=True
            )
        except Exception as e:
            return ToolResult(
                content=f"Error editing file: {str(e)}. Please check the file and arguments, then try again.",
                is_error=True
            )

    def _generate_diff(self, old: str, new: str, filename: str) -> str:
        """Generate unified diff."""
        old_lines = old.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)

        diff_lines = list(difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
            lineterm=''
        ))

        return ''.join(diff_lines[:50])  # Limit diff size

    def _find_first_changed_line(self, old: str, new: str) -> Optional[int]:
        """Find the first line that changed."""
        old_lines = old.splitlines()
        new_lines = new.splitlines()

        for i, (old_line, new_line) in enumerate(zip(old_lines, new_lines), start=1):
            if old_line != new_line:
                return i

        # Check if lines were added/removed at the end
        if len(old_lines) != len(new_lines):
            return min(len(old_lines), len(new_lines)) + 1

        return None

    def _find_similar_strings(self, content: str, target: str, n: int = 3) -> str:
        """Find similar strings in content."""
        lines = content.splitlines()
        target_lines = target.splitlines()

        if not target_lines:
            return ""

        # Find lines similar to the first line of target
        first_target_line = target_lines[0].strip()
        similar = []

        for i, line in enumerate(lines, start=1):
            ratio = difflib.SequenceMatcher(
                None, line.strip(), first_target_line).ratio()
            if ratio > 0.6:  # 60% similarity threshold
                similar.append((ratio, i, line))

        # Sort by similarity and take top n
        similar.sort(reverse=True, key=lambda x: x[0])
        results = []
        for ratio, line_num, line in similar[:n]:
            results.append(f"  Line {line_num}: {line.strip()[:80]}")

        return "\n".join(results) if results else ""
