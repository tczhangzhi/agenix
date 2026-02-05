"""Heartbeat extension - periodic agent wake-up."""

from pathlib import Path
from typing import Optional

from .service import HeartbeatService
from ...types import ExtensionAPI, EventType, SessionStartEvent, SessionEndEvent


async def setup(api: ExtensionAPI):
    """Setup heartbeat extension."""

    heartbeat_service: Optional[HeartbeatService] = None

    @api.on(EventType.SESSION_START)
    async def on_session_start(event: SessionStartEvent, ctx):
        """Start heartbeat service when session starts."""
        nonlocal heartbeat_service

        # Get workspace path
        workspace = Path(ctx.cwd) / ".agenix"
        workspace.mkdir(parents=True, exist_ok=True)

        # Create heartbeat callback
        async def on_heartbeat(prompt: str) -> str:
            """Execute heartbeat through agent."""
            response = ""
            async for _ in ctx.agent.prompt(prompt):
                pass  # Agent will handle output via events
            return response

        heartbeat_service = HeartbeatService(
            workspace=workspace,
            on_heartbeat=on_heartbeat,
            enabled=True
        )
        await heartbeat_service.start()

    @api.on(EventType.SESSION_END)
    async def on_session_end(event: SessionEndEvent, ctx):
        """Stop heartbeat service when session ends."""
        if heartbeat_service:
            heartbeat_service.stop()

    @api.on(EventType.SESSION_SHUTDOWN)
    async def on_session_shutdown(event, ctx):
        """Final cleanup on shutdown."""
        if heartbeat_service:
            heartbeat_service.stop()
