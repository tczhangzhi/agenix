"""Task Tool - Delegate tasks to specialized subagents.

This tool implements the "Agent as Tool" design pattern, allowing the main agent
to create and delegate to specialized subagents for focused execution.
"""

import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List

from ....tools.builtin.base import Tool, ToolResult


class TaskTool(Tool):
    """Task Tool - Create subagents to execute specialized tasks.

    This tool allows delegating tasks to subagents that can work independently
    on focused objectives without cluttering the main agent's context.

    Example:
        >>> task_tool = TaskTool()
        >>> result = await task_tool.execute(
        ...     tool_call_id="123",
        ...     arguments={
        ...         "task": "Find all API endpoints in the codebase",
        ...         "context": "Planning to document the API"
        ...     }
        ... )
    """

    def __init__(
        self,
        working_dir: str = ".",
        agent_id: Optional[str] = None,
        parent_chain: Optional[List[str]] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """Initialize Task Tool.

        Args:
            working_dir: Working directory for file operations
            agent_id: Unique ID of the current agent (for preventing circular calls)
            parent_chain: List of ancestor agent IDs (for preventing circular calls)
            model: Model to use for subagents (inherited from parent if not specified)
            api_key: API key for subagents
            base_url: Base URL for API calls
        """
        self.working_dir = working_dir
        self.agent_id = agent_id
        self.parent_chain = parent_chain or []
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

        super().__init__(
            name="task",
            description="""Delegate a task to a specialized subagent.

Use this tool when:
- You need to work on a focused subtask without cluttering your context
- The task would benefit from a fresh perspective
- You want to isolate the execution of a specific objective

The subagent will have access to the same tools and will execute independently.""",
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
            }
        )

    async def execute(
        self,
        tool_call_id: str,
        arguments: Dict[str, Any],
        on_update: Optional[Callable[[str], None]] = None,
    ) -> ToolResult:
        """Execute the task tool - create and run subagent.

        Args:
            tool_call_id: Unique ID for this tool call
            arguments: {"task": "...", "context": "..."}
            on_update: Optional progress callback

        Returns:
            ToolResult with subagent's output
        """
        task = arguments.get("task", "")
        context = arguments.get("context", "")

        # Validate arguments
        if not task:
            return ToolResult(
                content="Error: task parameter is required",
                is_error=True
            )

        # Report start
        if on_update:
            on_update("Starting subagent...")

        try:
            result = await self._execute_subagent(
                task=task,
                context=context,
                on_update=on_update
            )

            return result

        except Exception as e:
            return ToolResult(
                content=f"Error executing subagent: {str(e)}",
                is_error=True
            )

    async def _execute_subagent(
        self,
        task: str,
        context: str,
        on_update: Optional[Callable[[str], None]] = None
    ) -> ToolResult:
        """Execute a subagent.

        Creates a real subagent instance and executes the task.

        Args:
            task: Task description
            context: Additional context
            on_update: Progress callback

        Returns:
            ToolResult with subagent output
        """
        from ..core.agent import Agent, AgentConfig
        from .read import ReadTool
        from .write import WriteTool
        from .edit import EditTool
        from .bash import BashTool
        from .grep import GrepTool
        from .glob import GlobTool
        from .skill import SkillTool

        if on_update:
            on_update("Initializing subagent...")

        try:
            # Check for circular calls
            if self.agent_id and self.agent_id in self.parent_chain:
                return ToolResult(
                    content="Error: Circular agent call detected. This agent is already in the call chain.",
                    is_error=True
                )

            # Create tools for subagent
            tools = [
                ReadTool(working_dir=self.working_dir),
                WriteTool(working_dir=self.working_dir),
                EditTool(working_dir=self.working_dir),
                BashTool(working_dir=self.working_dir),
                GrepTool(working_dir=self.working_dir),
                GlobTool(working_dir=self.working_dir),
                SkillTool(working_dir=self.working_dir),
            ]

            # Add TaskTool so subagent can create its own subagents if needed
            tools.append(
                TaskTool(
                    working_dir=self.working_dir,
                    agent_id=None,  # Will be updated after subagent creation
                    parent_chain=self.parent_chain + ([self.agent_id] if self.agent_id else []),
                    model=self.model,
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
            )

            if on_update:
                on_update(f"Subagent has {len(tools)} tools available")

            # Build system prompt for subagent
            system_prompt = f"""You are a specialized subagent working on a focused task.

Your task: {task}

{"Additional context: " + context if context else ""}

Guidelines:
- Focus on completing the specific task assigned to you
- Be concise and efficient
- Use the available tools to accomplish your goal
- Report your findings or results clearly

Available tools: read, write, edit, bash, grep, glob, skill, task"""

            # Create subagent config
            config = AgentConfig(
                model=self.model or "gpt-4o",
                api_key=self.api_key,
                base_url=self.base_url,
                system_prompt=system_prompt,
                max_turns=10,
                max_tokens=8192,
            )

            # Create subagent with parent chain
            subagent = Agent(
                config=config,
                tools=tools,
                parent_chain=self.parent_chain + ([self.agent_id] if self.agent_id else [])
            )

            # Update TaskTool in subagent with the new agent_id
            for tool in tools:
                if isinstance(tool, TaskTool):
                    tool.agent_id = subagent.agent_id

            # Build full prompt
            full_prompt = task
            if context:
                full_prompt = f"Context: {context}\n\nTask: {task}"

            if on_update:
                on_update("Executing task...")

            # Collect subagent output
            output_parts = []
            tool_calls = []

            # Execute subagent
            async for event in subagent.prompt(full_prompt):
                # Collect text output
                from ..core.messages import MessageUpdateEvent, ToolExecutionEndEvent, AgentEndEvent

                if isinstance(event, MessageUpdateEvent):
                    output_parts.append(event.delta)
                    if on_update and event.delta:
                        on_update(event.delta)

                # Track tool calls
                elif isinstance(event, ToolExecutionEndEvent):
                    tool_calls.append({
                        "tool": event.tool_name,
                        "error": event.is_error
                    })

                # Done
                elif isinstance(event, AgentEndEvent):
                    break

            # Build result
            result_text = "".join(output_parts)

            # Add summary
            summary = f"""

---
**Subagent Execution Summary**
- Tools available: {len(tools)}
- Tools called: {len(tool_calls)}
- Output length: {len(result_text)} characters
"""

            if tool_calls:
                summary += "\n**Tool Calls:**\n"
                for i, call in enumerate(tool_calls, 1):
                    status = "❌ Error" if call["error"] else "✓"
                    summary += f"  {i}. {call['tool']} {status}\n"

            return ToolResult(
                content=result_text + summary,
                details={
                    "tools_available": len(tools),
                    "tools_called": len(tool_calls),
                    "output_length": len(result_text),
                }
            )

        except Exception as e:
            return ToolResult(
                content=f"Error executing subagent: {str(e)}",
                is_error=True
            )
