"""Memory system for persistent agent memory."""

from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional

from ....bus import MessageBus, MemoryUpdateEvent


def _today_date() -> str:
    """Get today's date in YYYY-MM-DD format."""
    return datetime.now().strftime("%Y-%m-%d")


def _ensure_dir(path: Path) -> Path:
    """Ensure a directory exists, creating it if necessary."""
    path.mkdir(parents=True, exist_ok=True)
    return path


class MemoryStore:
    """
    Memory system for the agent.

    Supports daily notes (memory/YYYY-MM-DD.md) and long-term memory (MEMORY.md).
    """

    def __init__(self, workspace: Path, bus: Optional[MessageBus] = None):
        """Initialize memory store.

        Args:
            workspace: Base workspace directory (e.g., .agenix)
            bus: Optional message bus for publishing events
        """
        self.workspace = workspace
        self.memory_dir = _ensure_dir(workspace / "memory")
        self.memory_file = self.memory_dir / "MEMORY.md"
        self.bus = bus

    def get_today_file(self) -> Path:
        """Get path to today's memory file."""
        return self.memory_dir / f"{_today_date()}.md"

    def read_today(self) -> str:
        """Read today's memory notes."""
        today_file = self.get_today_file()
        if today_file.exists():
            return today_file.read_text(encoding="utf-8")
        return ""

    def append_today(self, content: str) -> None:
        """Append content to today's memory notes."""
        today_file = self.get_today_file()

        if today_file.exists():
            existing = today_file.read_text(encoding="utf-8")
            content = existing + "\n" + content
        else:
            # Add header for new day
            header = f"# {_today_date()}\n\n"
            content = header + content

        today_file.write_text(content, encoding="utf-8")

        # Publish event to bus if available and we have a running loop
        if self.bus:
            self._try_publish_event(MemoryUpdateEvent(
                scope="today",
                content=content
            ))

    def read_long_term(self) -> str:
        """Read long-term memory (MEMORY.md)."""
        if self.memory_file.exists():
            return self.memory_file.read_text(encoding="utf-8")
        return ""

    def write_long_term(self, content: str) -> None:
        """Write to long-term memory (MEMORY.md)."""
        self.memory_file.write_text(content, encoding="utf-8")

        # Publish event to bus if available and we have a running loop
        if self.bus:
            self._try_publish_event(MemoryUpdateEvent(
                scope="long_term",
                content=content
            ))

    def _try_publish_event(self, event) -> None:
        """Try to publish event to bus if event loop is running."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(self.bus.publish(event))
        except RuntimeError:
            # No running event loop, skip event publishing
            pass

    def get_recent_memories(self, days: int = 7) -> str:
        """
        Get memories from the last N days.

        Args:
            days: Number of days to look back.

        Returns:
            Combined memory content.
        """
        memories = []
        today = datetime.now().date()

        for i in range(days):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            file_path = self.memory_dir / f"{date_str}.md"

            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                memories.append(content)

        return "\n\n---\n\n".join(memories)

    def list_memory_files(self) -> List[Path]:
        """List all memory files sorted by date (newest first)."""
        if not self.memory_dir.exists():
            return []

        files = list(self.memory_dir.glob("????-??-??.md"))
        return sorted(files, reverse=True)

    def get_memory_context(self) -> str:
        """
        Get memory context for the agent.

        Returns:
            Formatted memory context including long-term and recent memories.
        """
        parts = []

        # Long-term memory
        long_term = self.read_long_term()
        if long_term:
            parts.append("## Long-term Memory\n" + long_term)

        # Today's notes
        today = self.read_today()
        if today:
            parts.append("## Today's Notes\n" + today)

        return "\n\n".join(parts) if parts else ""
