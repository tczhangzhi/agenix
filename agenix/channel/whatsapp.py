"""WhatsApp channel implementation using WebSocket bridge."""

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Optional

from .base import BaseChannel
from ..bus import MessageBus


@dataclass
class WhatsAppConfig:
    """WhatsApp channel configuration."""
    enabled: bool = False
    bridge_url: str = "ws://localhost:3000"
    allow_from: Optional[list[str]] = None


class WhatsAppChannel(BaseChannel):
    """
    WhatsApp channel that connects to a Node.js bridge.

    The bridge uses @whiskeysockets/baileys to handle the WhatsApp Web protocol.
    Communication between Python and Node.js is via WebSocket.
    """

    name = "whatsapp"

    def __init__(self, config: WhatsAppConfig, bus: Optional[MessageBus] = None):
        super().__init__(config, bus)
        self.config: WhatsAppConfig = config
        self._ws = None
        self._connected = False

    async def start(self) -> None:
        """Start the WhatsApp channel by connecting to the bridge."""
        try:
            import websockets
        except ImportError:
            print("Error: 'websockets' package required for WhatsApp")
            print("Install with: pip install websockets")
            return

        bridge_url = self.config.bridge_url

        print(f"Connecting to WhatsApp bridge at {bridge_url}...")

        self._running = True

        # Subscribe to responses
        await self._subscribe_to_responses()

        while self._running:
            try:
                async with websockets.connect(bridge_url) as ws:
                    self._ws = ws
                    self._connected = True
                    print("✓ Connected to WhatsApp bridge")

                    # Listen for messages
                    async for message in ws:
                        try:
                            await self._handle_bridge_message(message)
                        except Exception as e:
                            print(f"Error handling bridge message: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._connected = False
                self._ws = None
                print(f"WhatsApp bridge connection error: {e}")

                if self._running:
                    print("Reconnecting in 5 seconds...")
                    await asyncio.sleep(5)

    async def stop(self) -> None:
        """Stop the WhatsApp channel."""
        self._running = False
        self._connected = False

        if self._ws:
            await self._ws.close()
            self._ws = None

    async def send(self, content: str, **kwargs) -> None:
        """Send a message through WhatsApp."""
        if not self._ws or not self._connected:
            print("Warning: WhatsApp bridge not connected")
            return

        chat_id = kwargs.get("chat_id") or kwargs.get("sender_id")
        if not chat_id:
            print("Error: No chat_id specified for WhatsApp message")
            return

        try:
            payload = {
                "type": "send",
                "to": chat_id,
                "text": content
            }
            await self._ws.send(json.dumps(payload))
        except Exception as e:
            print(f"Error sending WhatsApp message: {e}")

    async def _handle_bridge_message(self, raw: str) -> None:
        """Handle a message from the bridge."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            print(f"Invalid JSON from bridge: {raw[:100]}")
            return

        msg_type = data.get("type")

        if msg_type == "message":
            # Incoming message from WhatsApp
            sender = data.get("sender", "")
            content = data.get("content", "")

            # sender is typically: <phone>@s.whatsapp.net
            # Extract just the phone number as chat_id
            chat_id = sender.split("@")[0] if "@" in sender else sender

            # Handle voice transcription if it's a voice message
            if content == "[Voice Message]":
                print(f"Voice message received from {chat_id}")
                content = "[Voice Message: Transcription not available]"

            await self._handle_incoming_message(
                sender_id=chat_id,
                content=content,
                session_id=f"whatsapp:{chat_id}",
                metadata={
                    "message_id": data.get("id"),
                    "timestamp": data.get("timestamp"),
                    "is_group": data.get("isGroup", False),
                    "chat_id": sender  # Full JID for replies
                }
            )

        elif msg_type == "status":
            # Connection status update
            status = data.get("status")
            print(f"WhatsApp status: {status}")

            if status == "connected":
                self._connected = True
            elif status == "disconnected":
                self._connected = False

        elif msg_type == "qr":
            # QR code for authentication
            print("📱 Scan QR code in the bridge terminal to connect WhatsApp")

        elif msg_type == "error":
            print(f"WhatsApp bridge error: {data.get('error')}")
