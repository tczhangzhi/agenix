"""Cron extension - scheduled task execution."""

from pathlib import Path
from typing import Optional

from .service import CronService
from .types import CronSchedule
from ...types import ExtensionAPI, EventType, SessionStartEvent, SessionEndEvent, ToolDefinition


async def setup(api: ExtensionAPI):
    """Setup cron extension."""

    cron_service: Optional[CronService] = None

    @api.on(EventType.SESSION_START)
    async def on_session_start(event: SessionStartEvent, ctx):
        """Start cron service when session starts."""
        nonlocal cron_service

        # Get workspace path
        workspace = Path(ctx.cwd) / ".agenix"
        workspace.mkdir(parents=True, exist_ok=True)

        # Create cron service with agent callback
        async def on_cron_job(job):
            """Execute cron job through agent."""
            try:
                print(f"\n[Cron] Executing job: {job.name}")
                print(f"[Cron] Message: {job.payload.message}")
                print()

                # Execute job message through agent
                async for _ in ctx.agent.prompt(job.payload.message):
                    pass  # Agent will handle output via events

                print()
                print(f"[Cron] Job completed: {job.name}\n")
                return "Job completed successfully"
            except Exception as e:
                print(f"[Cron] Job failed: {e}\n")
                return f"Job failed: {e}"

        cron_service = CronService(workspace / "cron.json", on_job=on_cron_job)
        await cron_service.start()

    @api.on(EventType.SESSION_END)
    async def on_session_end(event: SessionEndEvent, ctx):
        """Stop cron service when session ends."""
        if cron_service:
            cron_service.stop()

    @api.on(EventType.SESSION_SHUTDOWN)
    async def on_session_shutdown(event, ctx):
        """Final cleanup on shutdown."""
        if cron_service:
            cron_service.stop()

    # Register cron tools
    api.register_tool(ToolDefinition(
        name="CronList",
        description="List all scheduled cron jobs",
        parameters={
            "type": "object",
            "properties": {
                "include_disabled": {
                    "type": "boolean",
                    "description": "Include disabled jobs in the list",
                    "default": False
                }
            }
        },
        execute=lambda params, ctx: _list_jobs(cron_service, params)
    ))

    api.register_tool(ToolDefinition(
        name="CronAdd",
        description="Add a new scheduled cron job",
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Job name"
                },
                "schedule": {
                    "type": "string",
                    "description": "Cron schedule expression or 'every:5m' for interval"
                },
                "message": {
                    "type": "string",
                    "description": "Message/prompt to execute"
                }
            },
            "required": ["name", "schedule", "message"]
        },
        execute=lambda params, ctx: _add_job(cron_service, params)
    ))

    api.register_tool(ToolDefinition(
        name="CronRemove",
        description="Remove a scheduled cron job by ID",
        parameters={
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "Job ID to remove"
                }
            },
            "required": ["job_id"]
        },
        execute=lambda params, ctx: _remove_job(cron_service, params)
    ))


async def _list_jobs(service: Optional[CronService], params: dict) -> str:
    """List cron jobs."""
    if not service:
        return "Error: Cron service not initialized"

    include_disabled = params.get("include_disabled", False)
    jobs = service.list_jobs(include_disabled=include_disabled)

    if not jobs:
        return "No cron jobs scheduled"

    result = []
    for job in jobs:
        status = "✓" if job.enabled else "✗"
        next_run = f"next: {job.state.next_run_at_ms}" if job.state.next_run_at_ms else "not scheduled"
        result.append(f"{status} {job.id}: {job.name} - {next_run}")

    return "\n".join(result)


async def _add_job(service: Optional[CronService], params: dict) -> str:
    """Add a cron job."""
    if not service:
        return "Error: Cron service not initialized"

    name = params["name"]
    schedule_str = params["schedule"]
    message = params["message"]

    # Parse schedule
    if schedule_str.startswith("every:"):
        # Interval format: "every:5m", "every:1h"
        interval_str = schedule_str[6:]
        if interval_str.endswith("m"):
            minutes = int(interval_str[:-1])
            every_ms = minutes * 60 * 1000
        elif interval_str.endswith("h"):
            hours = int(interval_str[:-1])
            every_ms = hours * 60 * 60 * 1000
        else:
            return f"Error: Invalid interval format '{interval_str}'"

        schedule = CronSchedule(kind="every", every_ms=every_ms)
    else:
        # Cron expression
        schedule = CronSchedule(kind="cron", expr=schedule_str)

    job = service.add_job(name=name, schedule=schedule, message=message)
    return f"Added cron job '{name}' ({job.id})"


async def _remove_job(service: Optional[CronService], params: dict) -> str:
    """Remove a cron job."""
    if not service:
        return "Error: Cron service not initialized"

    job_id = params["job_id"]
    removed = service.remove_job(job_id)

    if removed:
        return f"Removed cron job {job_id}"
    else:
        return f"Job {job_id} not found"
