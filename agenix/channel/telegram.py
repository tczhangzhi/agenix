"""Telegram channel implementation."""

import asyncio
from dataclasses import dataclass
from typing import Any, Optional

from .base import BaseChannel
from ..bus import MessageBus


@dataclass
class TelegramConfig:
    """Telegram channel configuration."""
    enabled: bool = False
    bot_token: str = ""
    allow_from: Optional[list[str]] = None


class TelegramChannel(BaseChannel):
    """
    Telegram channel using python-telegram-bot.

    Connects to Telegram Bot API and handles incoming/outgoing messages.
    """

    name = "telegram"

    def __init__(self, config: TelegramConfig, bus: Optional[MessageBus] = None):
        super().__init__(config, bus)
        self.config: TelegramConfig = config
        self._application = None

    async def start(self) -> None:
        """Start the Telegram channel."""
        try:
            from telegram import Update
            from telegram.ext import Application, MessageHandler, filters, ContextTypes
        except ImportError:
            print("Error: 'python-telegram-bot' package required for Telegram")
            print("Install with: pip install python-telegram-bot")
            return

        if not self.config.bot_token:
            print("Error: Telegram bot_token not configured")
            return

        print("Starting Telegram bot...")

        self._running = True

        # Subscribe to responses
        await self._subscribe_to_responses()

        # Create application
        self._application = Application.builder().token(self.config.bot_token).build()

        # Add message handler
        async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """Handle incoming Telegram messages."""
            if not update.message or not update.message.text:
                return

            sender_id = str(update.effective_user.id)
            chat_id = str(update.effective_chat.id)
            content = update.message.text

            await self._handle_incoming_message(
                sender_id=sender_id,
                content=content,
                session_id=f"telegram:{chat_id}",
                metadata={
                    "message_id": update.message.message_id,
                    "chat_id": chat_id,
                    "username": update.effective_user.username,
                    "first_name": update.effective_user.first_name
                }
            )

        self._application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        print("✓ Telegram bot started")

        # Run bot
        await self._application.run_polling(allowed_updates=Update.ALL_TYPES)

    async def stop(self) -> None:
        """Stop the Telegram channel."""
        self._running = False

        if self._application:
            await self._application.stop()
            await self._application.shutdown()
            self._application = None

    async def send(self, content: str, **kwargs) -> None:
        """Send a message through Telegram."""
        if not self._application:
            print("Warning: Telegram bot not initialized")
            return

        chat_id = kwargs.get("chat_id")
        if not chat_id:
            print("Error: No chat_id specified for Telegram message")
            return

        try:
            await self._application.bot.send_message(
                chat_id=chat_id,
                text=content,
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Error sending Telegram message: {e}")
