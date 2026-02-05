"""Base channel interface for communication platforms."""

from abc import ABC, abstractmethod
from typing import Any, Optional

from ..bus import MessageBus, AgentMessageEvent, AgentResponseEvent


class BaseChannel(ABC):
    """
    Abstract base class for channel implementations.

    Each channel (TUI, Telegram, WhatsApp, etc.) should implement this interface
    to integrate with the agenix message bus.
    """

    name: str = "base"

    def __init__(self, config: Any, bus: Optional[MessageBus] = None):
        """
        Initialize the channel.

        Args:
            config: Channel-specific configuration.
            bus: Optional message bus for communication.
        """
        self.config = config
        self.bus = bus
        self._running = False

    @abstractmethod
    async def start(self) -> None:
        """
        Start the channel and begin listening for messages.

        This should be a long-running async task that:
        1. Connects to the platform (if applicable)
        2. Listens for incoming messages
        3. Forwards messages to the bus
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the channel and clean up resources."""
        pass

    @abstractmethod
    async def send(self, content: str, **kwargs) -> None:
        """
        Send a message through this channel.

        Args:
            content: The message content to send.
            **kwargs: Channel-specific parameters.
        """
        pass

    def is_allowed(self, sender_id: str) -> bool:
        """
        Check if a sender is allowed to use this channel.

        Args:
            sender_id: The sender's identifier.

        Returns:
            True if allowed, False otherwise.
        """
        allow_list = getattr(self.config, "allow_from", None)

        # If no allow list, allow everyone
        if not allow_list:
            return True

        sender_str = str(sender_id)
        if sender_str in allow_list:
            return True
        if "|" in sender_str:
            for part in sender_str.split("|"):
                if part and part in allow_list:
                    return True
        return False

    async def _handle_incoming_message(
        self,
        sender_id: str,
        content: str,
        session_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Handle an incoming message from the platform.

        This method checks permissions and forwards to the bus.

        Args:
            sender_id: The sender's identifier.
            content: Message text content.
            session_id: Optional session identifier.
            metadata: Optional channel-specific metadata.
        """
        if not self.is_allowed(sender_id):
            print(f"Sender {sender_id} not allowed")
            return

        if self.bus:
            # Publish to bus
            await self.bus.publish(AgentMessageEvent(
                message=content,
                session_id=session_id or f"{self.name}:{sender_id}",
                context={
                    "channel": self.name,
                    "sender_id": sender_id,
                    **(metadata or {})
                }
            ))

    async def _subscribe_to_responses(self) -> None:
        """Subscribe to agent response events from the bus."""
        if self.bus:
            async def on_response(event: AgentResponseEvent):
                # Check if this response is for our channel
                if event.context.get("channel") == self.name:
                    await self.send(event.response, **event.context)

            self.bus.subscribe("agent_response", on_response)

    @property
    def is_running(self) -> bool:
        """Check if the channel is running."""
        return self._running
