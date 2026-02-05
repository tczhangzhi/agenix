"""CLI channel extension - session lifecycle hooks."""

from ..types import ExtensionAPI, EventType, SessionEndEvent


async def setup(api: ExtensionAPI):
    """Setup CLI channel extension."""

    session_id: str = ""

    @api.on(EventType.SESSION_START)
    async def on_session_start(event, ctx):
        """Track session start."""
        nonlocal session_id
        # Session ID will be set by CLI
        pass

    @api.on(EventType.SESSION_END)
    async def on_session_end(event: SessionEndEvent, ctx):
        """Show resume hint on session end."""
        # This will be handled by CLI for now
        # In the future, we can move more CLI logic here
        pass
