"""Safety extension - example extension that blocks dangerous operations.

This demonstrates how extensions can:
1. Block dangerous tool calls
2. Customize compaction behavior
3. Inject context modifications
"""

from ...types import (
    ExtensionAPI,
    EventType,
    ToolCallEvent,
    BeforeCompactEvent,
    ContextEvent
)


async def setup(api: ExtensionAPI):
    """Setup safety extension."""

    # Dangerous paths that should not be modified
    DANGEROUS_PATHS = ["/etc", "/sys", "/usr", "/bin", "/sbin"]

    @api.on(EventType.TOOL_CALL)
    async def on_tool_call(event: ToolCallEvent, ctx):
        """Block dangerous tool operations."""
        tool_name = event.tool_name
        args = event.args

        # Block bash commands that touch system directories
        if tool_name == "bash":
            command = args.get("command", "")
            if any(path in command for path in DANGEROUS_PATHS):
                event.cancel()
                ctx.notify(
                    f"Blocked dangerous command: {command}",
                    "warning"
                )
                return

        # Block write/edit to system files
        if tool_name in ["write", "edit"]:
            file_path = args.get("file_path", "")
            if any(file_path.startswith(path) for path in DANGEROUS_PATHS):
                event.cancel()
                ctx.notify(
                    f"Blocked system file modification: {file_path}",
                    "error"
                )
                return

    @api.on(EventType.BEFORE_COMPACT)
    async def on_before_compact(event: BeforeCompactEvent, ctx):
        """Customize compaction instructions."""
        # Tell the LLM to preserve important information during compaction
        event.custom_instructions = (
            "When summarizing, preserve all file paths and tool names. "
            "Keep security warnings and error messages."
        )

    @api.on(EventType.CONTEXT)
    async def on_context(event: ContextEvent, ctx):
        """Inject a system message before LLM sees context."""
        # Note: This is disabled by default, just an example
        # To enable, uncomment the following lines:
        #
        # from agenix.core.messages import SystemMessage
        # event.messages.insert(0, SystemMessage(
        #     content="Always explain your reasoning for file modifications."
        # ))
        pass
