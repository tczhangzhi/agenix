"""Subagent extension - delegate tasks to specialized subagents.

Based on pi-mono's subagent design, but simplified for Python/agenix.

Features:
- Isolated context per subagent
- Parallel execution support
- Specialized agent types (scout, planner, worker, reviewer)
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
import subprocess
import json
import asyncio

from .tool import TaskTool  # Reuse existing task tool as base
from ...types import ExtensionAPI, EventType, SessionStartEvent, ToolDefinition


async def setup(api: ExtensionAPI):
    """Setup subagent extension."""

    task_tool = None

    @api.on(EventType.SESSION_START)
    async def on_session_start(event: SessionStartEvent, ctx):
        """Initialize task/subagent tool when session starts."""
        nonlocal task_tool

        # Get agent configuration
        task_tool = TaskTool(
            working_dir=ctx.cwd,
            agent_id=ctx.agent.agent_id,
            parent_chain=[],
            model=ctx.agent.config.model,
            api_key=ctx.agent.config.api_key,
            base_url=ctx.agent.config.base_url,
        )

    # Register subagent tool (single task mode)
    api.register_tool(ToolDefinition(
        name="subagent",
        description="Delegate a task to a specialized subagent with isolated context",
        parameters={
            "type": "object",
            "properties": {
                "agent_type": {
                    "type": "string",
                    "enum": ["scout", "planner", "worker", "reviewer"],
                    "description": "Type of subagent: scout (fast recon), planner (create plans), worker (implement), reviewer (code review)"
                },
                "task": {
                    "type": "string",
                    "description": "Task description for the subagent"
                },
                "context": {
                    "type": "string",
                    "description": "Optional context to provide to the subagent"
                }
            },
            "required": ["agent_type", "task"]
        },
        execute=lambda params, ctx: _execute_subagent(task_tool, params, ctx)
    ))

    # Register parallel subagent tool
    api.register_tool(ToolDefinition(
        name="subagent_parallel",
        description="Run multiple subagents in parallel (max 4 concurrent)",
        parameters={
            "type": "object",
            "properties": {
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "agent_type": {"type": "string", "enum": ["scout", "planner", "worker", "reviewer"]},
                            "task": {"type": "string"}
                        },
                        "required": ["agent_type", "task"]
                    },
                    "maxItems": 8,
                    "description": "List of tasks to run in parallel (max 8 tasks)"
                }
            },
            "required": ["tasks"]
        },
        execute=lambda params, ctx: _execute_parallel(task_tool, params, ctx)
    ))


async def _execute_subagent(tool: Optional[TaskTool], params: dict, ctx) -> str:
    """Execute a single subagent task."""
    if not tool:
        return "Error: Subagent tool not initialized"

    from ....tools.builtin.base import ToolResult

    agent_type = params.get("agent_type", "worker")
    task = params["task"]
    context = params.get("context", "")

    # Add agent type prefix to task
    full_task = f"[{agent_type.upper()}] {task}"
    if context:
        full_task = f"{full_task}\n\nContext:\n{context}"

    # Execute using existing TaskTool
    result = await tool.execute(
        tool_call_id="",
        arguments={"task": full_task},
        on_update=None
    )

    if isinstance(result, ToolResult):
        return f"[Subagent: {agent_type}]\n{result.content}"
    return str(result)


async def _execute_parallel(tool: Optional[TaskTool], params: dict, ctx) -> str:
    """Execute multiple subagent tasks in parallel."""
    if not tool:
        return "Error: Subagent tool not initialized"

    tasks = params.get("tasks", [])
    if not tasks:
        return "Error: No tasks provided"

    if len(tasks) > 8:
        return "Error: Maximum 8 parallel tasks allowed"

    # Execute tasks with controlled concurrency (max 4 concurrent)
    results = []
    semaphore = asyncio.Semaphore(4)  # Max 4 concurrent

    async def run_task(task_params: dict, index: int):
        async with semaphore:
            agent_type = task_params.get("agent_type", "worker")
            task_desc = task_params["task"]

            print(f"[{index+1}/{len(tasks)}] Starting {agent_type}: {task_desc[:50]}...")

            result = await _execute_subagent(tool, task_params, ctx)
            return f"Task {index+1}: {result}"

    # Run all tasks
    task_coros = [run_task(t, i) for i, t in enumerate(tasks)]
    results = await asyncio.gather(*task_coros, return_exceptions=True)

    # Format results
    output = [f"Executed {len(tasks)} subagents in parallel:\n"]
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            output.append(f"\n{i+1}. ERROR: {str(result)}")
        else:
            output.append(f"\n{i+1}. {result}")

    return "\n".join(output)
