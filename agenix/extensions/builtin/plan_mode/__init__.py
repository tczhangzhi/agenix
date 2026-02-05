"""Plan mode extension - structured planning before implementation.

Based on pi-mono's plan-mode design, this extension provides:
- Read-only exploration during planning phase
- Structured plan extraction with numbered steps
- Progress tracking with [DONE:n] markers
- /plan and /todos commands for plan management
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
import re
import json

from ...types import (
    ExtensionAPI,
    EventType,
    SessionStartEvent,
    BeforeAgentStartEvent,
    ToolCallEvent,
    CommandDefinition,
    ToolDefinition,
)


# Planning state
class PlanState:
    """Tracks planning mode state."""

    def __init__(self):
        self.is_planning = False
        self.plan_steps: List[str] = []
        self.completed_steps: List[int] = []
        self.plan_file: Optional[Path] = None

    def extract_plan(self, text: str) -> bool:
        """Extract plan from agent response.

        Looks for:
        # Plan
        1. Step one
        2. Step two
        3. Step three

        Returns:
            True if plan was extracted
        """
        # Look for Plan: section with numbered steps
        plan_pattern = r'(?:^|\n)#+\s*Plan\s*\n((?:\d+\.\s+.+\n?)+)'
        match = re.search(plan_pattern, text, re.MULTILINE | re.IGNORECASE)

        if match:
            plan_text = match.group(1)
            # Extract numbered steps
            steps = re.findall(r'^\d+\.\s+(.+)$', plan_text, re.MULTILINE)
            if steps:
                self.plan_steps = steps
                self.completed_steps = []
                return True

        return False

    def update_progress(self, text: str) -> None:
        """Update progress from [DONE:n] markers.

        Example: [DONE:1,2,3] marks steps 1, 2, 3 as complete
        """
        done_pattern = r'\[DONE:([0-9,\s]+)\]'
        matches = re.findall(done_pattern, text)

        for match in matches:
            step_nums = [int(n.strip()) for n in match.split(',') if n.strip().isdigit()]
            for num in step_nums:
                if num not in self.completed_steps:
                    self.completed_steps.append(num)

    def get_plan_summary(self) -> str:
        """Get formatted plan with progress."""
        if not self.plan_steps:
            return "No plan created yet."

        lines = ["**Current Plan:**\n"]
        for i, step in enumerate(self.plan_steps, 1):
            status = "✓" if i in self.completed_steps else " "
            lines.append(f"{i}. [{status}] {step}")

        completed = len(self.completed_steps)
        total = len(self.plan_steps)
        lines.append(f"\nProgress: {completed}/{total} steps completed")

        return "\n".join(lines)


async def setup(api: ExtensionAPI):
    """Setup plan mode extension."""

    state = PlanState()
    workspace = Path(".agenix")
    workspace.mkdir(parents=True, exist_ok=True)

    # Bash commands allowed during planning (read-only operations)
    ALLOWED_BASH_COMMANDS = {
        'ls', 'cat', 'head', 'tail', 'grep', 'find', 'tree',
        'git status', 'git log', 'git diff', 'git branch',
        'pwd', 'which', 'whoami', 'date', 'echo',
        'npm list', 'pip list', 'python --version', 'node --version',
    }

    def is_bash_allowed(command: str) -> bool:
        """Check if bash command is allowed during planning."""
        command = command.strip()
        # Allow if command starts with any allowed command
        for allowed in ALLOWED_BASH_COMMANDS:
            if command.startswith(allowed):
                return True
        return False

    @api.on(EventType.SESSION_START)
    async def on_session_start(event: SessionStartEvent, ctx):
        """Initialize plan mode state."""
        nonlocal state
        state = PlanState()
        state.plan_file = workspace / "current_plan.md"

    @api.on(EventType.BEFORE_AGENT_START)
    async def on_before_agent_start(event: BeforeAgentStartEvent, ctx):
        """Inject planning instructions if in plan mode."""
        if state.is_planning:
            planning_prompt = """
**PLANNING MODE ACTIVE**

You are in planning mode. Your goal is to:
1. Explore the codebase using read-only tools (read, grep, glob, bash ls/cat/git)
2. Create a structured plan with numbered steps
3. DO NOT make any changes yet (no write, edit, or destructive bash commands)

When ready, output your plan in this format:

# Plan
1. First step description
2. Second step description
3. Third step description
...

After creating the plan, wait for user approval before proceeding to implementation.

Available read-only operations:
- read: Read file contents
- grep: Search for patterns
- glob: Find files by pattern
- bash: ls, cat, git status, git log, etc.

BLOCKED operations during planning:
- write: Creating new files
- edit: Modifying existing files
- bash: Any destructive commands (rm, mv, etc.)

Focus on understanding the codebase and designing a clear implementation plan.
"""
            # Inject planning instructions
            event.messages_to_inject.append({
                "role": "system",
                "content": planning_prompt
            })

    @api.on(EventType.TOOL_CALL)
    async def on_tool_call(event: ToolCallEvent, ctx):
        """Block destructive operations during planning."""
        if not state.is_planning:
            return

        tool_name = event.tool_name

        # Block write operations
        if tool_name in ["write", "edit"]:
            event.cancel()
            ctx.notify(f"🚫 {tool_name} is blocked during planning mode. Create a plan first.", "warning")
            return

        # Block destructive bash commands
        if tool_name == "bash":
            command = event.args.get("command", "")
            if not is_bash_allowed(command):
                event.cancel()
                ctx.notify(f"🚫 Command '{command}' is blocked during planning. Only read-only commands allowed.", "warning")
                return

    @api.on(EventType.MESSAGE_END)
    async def on_message_end(event, ctx):
        """Extract plan from agent messages."""
        if not state.is_planning:
            return

        # Try to extract plan from message
        if hasattr(event, 'content'):
            content = event.content
            if state.extract_plan(content):
                # Save plan to file
                if state.plan_file:
                    plan_text = state.get_plan_summary()
                    state.plan_file.write_text(plan_text)
                    ctx.notify(f"✓ Plan extracted and saved to {state.plan_file.name}", "success")

            # Update progress markers
            state.update_progress(content)

    # Register /plan command
    api.register_command(CommandDefinition(
        name="plan",
        description="Enter or exit planning mode",
        handler=lambda args, ctx: handle_plan_command(args, ctx, state)
    ))

    # Register /todos command
    api.register_command(CommandDefinition(
        name="todos",
        description="Show current plan and progress",
        handler=lambda args, ctx: handle_todos_command(args, ctx, state)
    ))

    # Register plan tool for programmatic access
    api.register_tool(ToolDefinition(
        name="PlanStatus",
        description="Get current plan status and progress",
        parameters={
            "type": "object",
            "properties": {}
        },
        execute=lambda params, ctx: _get_plan_status(state)
    ))


async def handle_plan_command(args: str, ctx, state: PlanState) -> str:
    """Handle /plan command to enter/exit planning mode."""
    if not state.is_planning:
        # Enter planning mode
        state.is_planning = True
        state.plan_steps = []
        state.completed_steps = []
        return """
🎯 **Entering Planning Mode**

In planning mode, you can:
- Explore the codebase (read, grep, glob, bash ls/cat/git)
- Design your implementation approach
- Create a structured plan with numbered steps

Blocked operations:
- write, edit (file modifications)
- Destructive bash commands

When ready, create your plan in this format:

# Plan
1. First step
2. Second step
3. Third step

Use /plan again to exit planning mode and start implementation.
"""
    else:
        # Exit planning mode
        state.is_planning = False
        summary = state.get_plan_summary()
        return f"""
✓ **Exiting Planning Mode**

{summary}

You can now proceed with implementation. Use /todos to track progress.
"""


async def handle_todos_command(args: str, ctx, state: PlanState) -> str:
    """Handle /todos command to show plan progress."""
    return state.get_plan_summary()


async def _get_plan_status(state: PlanState) -> str:
    """Get plan status for tool calls."""
    if not state.plan_steps:
        return json.dumps({
            "has_plan": False,
            "message": "No plan created yet"
        })

    return json.dumps({
        "has_plan": True,
        "is_planning": state.is_planning,
        "total_steps": len(state.plan_steps),
        "completed_steps": len(state.completed_steps),
        "progress": f"{len(state.completed_steps)}/{len(state.plan_steps)}",
        "steps": [
            {
                "number": i,
                "description": step,
                "completed": i in state.completed_steps
            }
            for i, step in enumerate(state.plan_steps, 1)
        ]
    })
