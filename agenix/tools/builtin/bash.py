"""Bash command execution tool."""

import asyncio
import os
import signal
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .base import Tool, ToolResult


class BashTool(Tool):
    """Execute bash commands."""

    def __init__(self, working_dir: str = ".", timeout: int = 120):
        self.working_dir = working_dir
        self.timeout = timeout
        super().__init__(
            name="bash",
            description=(
                "Execute bash commands (ls, grep, find, git, npm, etc.). "
                "Returns stdout, stderr, and exit code. Commands run in the working directory. "
                "Supports piping and redirection. Timeout after 120 seconds."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The bash command to execute"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": f"Timeout in seconds (default: {timeout}, max: 600)",
                        "default": timeout
                    }
                },
                "required": ["command"]
            }
        )

    async def execute(
        self,
        tool_call_id: str,
        arguments: Dict[str, Any],
        on_update: Optional[Callable[[str], None]] = None,
    ) -> ToolResult:
        """Execute bash command."""
        command = arguments["command"]
        timeout = min(arguments.get("timeout", self.timeout), 600)

        try:
            # Create process
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.working_dir,
                env=os.environ.copy(),
            )

            # Stream output with timeout
            stdout_lines = []
            stderr_lines = []
            output_size = 0
            max_output_size = 1_000_000  # 1MB limit

            async def read_stream(stream, lines, name):
                nonlocal output_size
                while True:
                    try:
                        line = await stream.readline()
                        if not line:
                            break

                        decoded = line.decode('utf-8', errors='replace')
                        lines.append(decoded)
                        output_size += len(decoded)

                        # Send progress update
                        if on_update:
                            on_update(f"[{name}] {decoded.rstrip()}")

                        # Check size limit
                        if output_size > max_output_size:
                            break
                    except Exception:
                        break

            # Read both streams concurrently with timeout
            try:
                await asyncio.wait_for(
                    asyncio.gather(
                        read_stream(process.stdout, stdout_lines, "stdout"),
                        read_stream(process.stderr, stderr_lines, "stderr"),
                    ),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                # Kill process on timeout
                try:
                    process.kill()
                    await process.wait()
                except:
                    pass

                return ToolResult(
                    content=f"Error: Command timed out after {timeout} seconds\n\n"
                    f"Partial stdout:\n{''.join(stdout_lines[-50:])}\n\n"
                    f"Partial stderr:\n{''.join(stderr_lines[-50:])}",
                    is_error=True,
                    details={"timeout": True, "timeout_seconds": timeout}
                )

            # Wait for process to complete
            exit_code = await process.wait()

            # Format output
            stdout_text = ''.join(stdout_lines)
            stderr_text = ''.join(stderr_lines)

            # Truncate if too large
            truncated = False
            if len(stdout_text) > max_output_size:
                stdout_text = stdout_text[:max_output_size] + \
                    "\n\n[Output truncated...]"
                truncated = True

            # Build result
            result_parts = []
            result_parts.append(f"Command: {command}")
            result_parts.append(f"Exit code: {exit_code}")

            if stdout_text:
                result_parts.append(f"\nStdout:\n{stdout_text}")

            if stderr_text:
                result_parts.append(f"\nStderr:\n{stderr_text}")

            is_error = exit_code != 0

            return ToolResult(
                content="\n".join(result_parts),
                is_error=is_error,
                details={
                    "exit_code": exit_code,
                    "truncated": truncated,
                    "command": command
                }
            )

        except FileNotFoundError:
            return ToolResult(
                content=f"Error: Command not found or bash not available",
                is_error=True
            )
        except Exception as e:
            return ToolResult(
                content=f"Error executing command: {str(e)}",
                is_error=True
            )
