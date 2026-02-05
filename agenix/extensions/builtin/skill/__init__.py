"""Skill extension - load specialized instructions from SKILL.md files."""

from .tool import SkillTool
from ...types import ExtensionAPI, EventType, SessionStartEvent, ToolDefinition


async def setup(api: ExtensionAPI):
    """Setup skill extension."""

    skill_tool = None

    @api.on(EventType.SESSION_START)
    async def on_session_start(event: SessionStartEvent, ctx):
        """Initialize skill tool when session starts."""
        nonlocal skill_tool

        skill_tool = SkillTool(working_dir=ctx.cwd)

    # Register skill tool
    api.register_tool(ToolDefinition(
        name="skill",
        description="Load specialized instructions from SKILL.md files in subdirectories",
        parameters={
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "Name of the skill to load (subdirectory name)"
                }
            },
            "required": ["skill_name"]
        },
        execute=lambda params, ctx: _execute_skill(skill_tool, params)
    ))


async def _execute_skill(tool: SkillTool, params: dict) -> str:
    """Execute skill tool."""
    if not tool:
        return "Error: Skill tool not initialized"

    from ....tools.builtin.base import ToolResult

    result = await tool.execute(
        tool_call_id="",
        arguments=params,
        on_update=None
    )

    if isinstance(result, ToolResult):
        return result.content
    return str(result)
