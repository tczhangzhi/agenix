"""Memory extension - persistent memory store."""

from pathlib import Path
from typing import Optional

from .service import MemoryStore
from ...types import ExtensionAPI, EventType, SessionStartEvent, ToolDefinition


async def setup(api: ExtensionAPI):
    """Setup memory extension."""

    memory_store: Optional[MemoryStore] = None

    @api.on(EventType.SESSION_START)
    async def on_session_start(event: SessionStartEvent, ctx):
        """Initialize memory store when session starts."""
        nonlocal memory_store

        # Get workspace path
        workspace = Path(ctx.cwd) / ".agenix"
        workspace.mkdir(parents=True, exist_ok=True)

        memory_store = MemoryStore(workspace)

    # Register memory tools
    api.register_tool(ToolDefinition(
        name="MemoryRead",
        description="Read from memory store (daily notes or long-term memory)",
        parameters={
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["today", "long_term", "recent"],
                    "description": "Memory scope: 'today' for today's notes, 'long_term' for MEMORY.md, 'recent' for last 7 days"
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days to look back (only for 'recent' scope)",
                    "default": 7
                }
            },
            "required": ["scope"]
        },
        execute=lambda params, ctx: _read_memory(memory_store, params)
    ))

    api.register_tool(ToolDefinition(
        name="MemoryWrite",
        description="Write to memory store (append to today's notes or update long-term memory)",
        parameters={
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["today", "long_term"],
                    "description": "Memory scope: 'today' to append to today's notes, 'long_term' to write MEMORY.md"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write"
                }
            },
            "required": ["scope", "content"]
        },
        execute=lambda params, ctx: _write_memory(memory_store, params)
    ))


async def _read_memory(store: Optional[MemoryStore], params: dict) -> str:
    """Read from memory store."""
    if not store:
        return "Error: Memory store not initialized"

    scope = params.get("scope")

    if scope == "today":
        content = store.read_today()
        return content if content else "No notes for today yet."

    elif scope == "long_term":
        content = store.read_long_term()
        return content if content else "No long-term memory yet."

    elif scope == "recent":
        days = params.get("days", 7)
        content = store.get_recent_memories(days=days)
        return content if content else f"No memories found for the last {days} days."

    else:
        return f"Error: Unknown scope '{scope}'"


async def _write_memory(store: Optional[MemoryStore], params: dict) -> str:
    """Write to memory store."""
    if not store:
        return "Error: Memory store not initialized"

    scope = params.get("scope")
    content = params.get("content", "")

    if not content:
        return "Error: No content provided"

    if scope == "today":
        store.append_today(content)
        return f"Appended to today's notes ({len(content)} chars)"

    elif scope == "long_term":
        store.write_long_term(content)
        return f"Updated long-term memory ({len(content)} chars)"

    else:
        return f"Error: Unknown scope '{scope}'"
