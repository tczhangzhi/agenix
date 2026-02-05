"""Task extension - delegate tasks to specialized subagents."""

from pathlib import Path
from typing import Optional

from .task import TaskTool
from ...types import ExtensionAPI, EventType, SessionStartEvent, ToolDefinition


async def setup(api: ExtensionAPI):
    """Setup task extension."""

    task_tool = None

    @api.on(EventType.SESSION_START)
    async def on_session_start(event: SessionStartEvent, ctx):
        """Initialize task tool when session starts."""
        nonlocal task_tool

        # Get agent configuration
        task_tool = TaskTool(
            working_dir=ctx.cwd,
            agent_id=getattr(ctx.agent, 'agent_id', None),
            parent_chain=[],
            model=ctx.agent.config.model if hasattr(ctx.agent, 'config') else None,
            api_key=ctx.agent.config.api_key if hasattr(ctx.agent, 'config') else None,
            base_url=ctx.agent.config.base_url if hasattr(ctx.agent, 'config') else None,
        )

    # Register task tool
    api.register_tool(ToolDefinition(
        name="task",
        description="Delegate a task to a specialized subagent with isolated context",
        parameters={
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Clear description of the task for the subagent"
                },
                "context": {
                    "type": "string",
                    "description": "Optional additional context or information needed for the task"
                }
            },
            "required": ["task"]
        },
        execute=lambda params, ctx: _execute_task(task_tool, params, ctx)
    ))


async def _execute_task(tool: Optional[TaskTool], params: dict, ctx) -> str:
    """Execute task tool."""
    if not tool:
        return "Error: Task tool not initialized"

    from ....tools.builtin.base import ToolResult

    result = await tool.execute(
        tool_call_id="",
        arguments=params,
        on_update=None
    )

    if isinstance(result, ToolResult):
        return result.content
    return str(result)
