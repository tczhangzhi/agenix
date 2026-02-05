"""Grep/search tool."""

import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .base import Tool, ToolResult


class GrepTool(Tool):
    """Search for patterns in files."""

    def __init__(self, working_dir: str = "."):
        self.working_dir = working_dir
        super().__init__(
            name="grep",
            description=(
                "Search file contents for patterns using regular expressions. "
                "Respects .gitignore. Supports filtering by file patterns (*.py, *.js). "
                "Shows matching lines with context. Fast for finding code across projects."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Regular expression pattern to search for"
                    },
                    "path": {
                        "type": "string",
                        "description": "File or directory to search in (default: current directory)",
                        "default": "."
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Glob pattern to filter files (e.g., '*.py', '*.{js,ts}')",
                    },
                    "ignore_case": {
                        "type": "boolean",
                        "description": "Case insensitive search (default: false)",
                        "default": False
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "Number of lines to show before and after each match (default: 0)",
                        "default": 0
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of matches to return (default: 100)",
                        "default": 100
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
        """Execute grep operation."""
        pattern = arguments["pattern"]
        path = arguments.get("path", ".")
        file_pattern = arguments.get("file_pattern")
        ignore_case = arguments.get("ignore_case", False)
        context_lines = arguments.get("context_lines", 0)
        max_results = arguments.get("max_results", 100)

        # Resolve path
        if not os.path.isabs(path):
            path = os.path.join(self.working_dir, path)

        try:
            # Compile regex
            flags = re.IGNORECASE if ignore_case else 0
            regex = re.compile(pattern, flags)

            # Find files to search
            files_to_search = []
            if os.path.isfile(path):
                files_to_search = [path]
            elif os.path.isdir(path):
                files_to_search = self._find_files(path, file_pattern)
            else:
                return ToolResult(
                    content=f"Error: Path not found: {path}",
                    is_error=True
                )

            # Search files
            matches = []
            files_searched = 0

            for file_path in files_to_search:
                if len(matches) >= max_results:
                    break

                if on_update:
                    on_update(f"Searching: {file_path}")

                file_matches = self._search_file(
                    file_path, regex, context_lines, max_results - len(matches)
                )
                if file_matches:
                    matches.extend(file_matches)

                files_searched += 1

            # Format results
            if not matches:
                return ToolResult(
                    content=f"No matches found for pattern '{pattern}' in {files_searched} files"
                )

            result_lines = [f"Found {len(matches)} matches in {files_searched} files:\n"]

            current_file = None
            for match in matches:
                if match['file'] != current_file:
                    current_file = match['file']
                    result_lines.append(f"\n{current_file}:")

                line_num = match['line_num']
                line = match['line'].rstrip()
                result_lines.append(f"  {line_num:6d}: {line}")

                # Add context lines
                for ctx_line_num, ctx_line in match.get('context', []):
                    result_lines.append(f"  {ctx_line_num:6d}: {ctx_line.rstrip()}")

            return ToolResult(
                content="\n".join(result_lines),
                details={
                    "matches": len(matches),
                    "files_searched": files_searched
                }
            )

        except re.error as e:
            return ToolResult(
                content=f"Error: Invalid regex pattern: {str(e)}",
                is_error=True
            )
        except Exception as e:
            return ToolResult(
                content=f"Error during search: {str(e)}",
                is_error=True
            )

    def _find_files(self, root: str, pattern: Optional[str] = None) -> List[str]:
        """Find files matching pattern."""
        files = []

        # Convert glob pattern to regex if provided
        if pattern:
            # Simple glob to regex conversion
            regex_pattern = pattern.replace('.', r'\.')
            regex_pattern = regex_pattern.replace('*', '.*')
            regex_pattern = regex_pattern.replace('?', '.')
            file_regex = re.compile(f"^{regex_pattern}$")
        else:
            file_regex = None

        for dirpath, dirnames, filenames in os.walk(root):
            # Skip hidden directories and common ignore patterns
            dirnames[:] = [d for d in dirnames if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv', '.git']]

            for filename in filenames:
                # Skip hidden files
                if filename.startswith('.'):
                    continue

                # Check pattern
                if file_regex and not file_regex.match(filename):
                    continue

                files.append(os.path.join(dirpath, filename))

                # Limit total files
                if len(files) >= 1000:
                    return files

        return files

    def _search_file(
        self,
        file_path: str,
        regex: re.Pattern,
        context_lines: int,
        max_matches: int
    ) -> List[Dict[str, Any]]:
        """Search a single file."""
        matches = []

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            for i, line in enumerate(lines, start=1):
                if len(matches) >= max_matches:
                    break

                if regex.search(line):
                    match = {
                        'file': file_path,
                        'line_num': i,
                        'line': line,
                    }

                    # Add context lines
                    if context_lines > 0:
                        context = []
                        # Before
                        for j in range(max(0, i - context_lines - 1), i - 1):
                            context.append((j + 1, lines[j]))
                        # After
                        for j in range(i, min(len(lines), i + context_lines)):
                            context.append((j + 1, lines[j]))
                        match['context'] = context

                    matches.append(match)

        except Exception:
            # Skip files that can't be read
            pass

        return matches
