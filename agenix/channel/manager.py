"""Channel manager for coordinating communication platforms."""

import asyncio
from typing import Any, Optional

from .base import BaseChannel
from ..bus import MessageBus


class ChannelManager:
    """
    Manages channels and coordinates message routing.

    Responsibilities:
    - Initialize enabled channels (TUI, Telegram, WhatsApp, etc.)
    - Start/stop channels
    - Route messages between agent and channels
    """

    def __init__(self, bus: Optional[MessageBus] = None):
        """
        Initialize the channel manager.

        Args:
            bus: Optional message bus for communication.
        """
        self.bus = bus
        self.channels: dict[str, BaseChannel] = {}
        self._tasks: list[asyncio.Task] = []

    def register(self, channel: BaseChannel) -> None:
        """
        Register a channel with the manager.

        Args:
            channel: Channel instance to register.
        """
        self.channels[channel.name] = channel
        print(f"Registered channel: {channel.name}")

    async def start_all(self) -> None:
        """Start all registered channels."""
        if not self.channels:
            print("Warning: No channels registered")
            return

        print(f"Starting {len(self.channels)} channel(s)...")

        # Start all channels
        for name, channel in self.channels.items():
            print(f"  Starting {name}...")
            task = asyncio.create_task(channel.start())
            self._tasks.append(task)

        print("All channels started")

    async def stop_all(self) -> None:
        """Stop all channels."""
        print("Stopping all channels...")

        # Stop all channels
        for name, channel in self.channels.items():
            try:
                await channel.stop()
                print(f"  Stopped {name}")
            except Exception as e:
                print(f"  Error stopping {name}: {e}")

        # Cancel all tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._tasks.clear()
        print("All channels stopped")

    def get_channel(self, name: str) -> Optional[BaseChannel]:
        """Get a channel by name."""
        return self.channels.get(name)

    def get_status(self) -> dict[str, Any]:
        """Get status of all channels."""
        return {
            name: {
                "enabled": True,
                "running": channel.is_running
            }
            for name, channel in self.channels.items()
        }

    @property
    def enabled_channels(self) -> list[str]:
        """Get list of enabled channel names."""
        return list(self.channels.keys())

    async def wait_for_all(self) -> None:
        """Wait for all channel tasks to complete."""
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
