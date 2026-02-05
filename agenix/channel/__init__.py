"""Channel package for multi-platform communication."""

from .base import BaseChannel
from .manager import ChannelManager
from .telegram import TelegramChannel, TelegramConfig
from .whatsapp import WhatsAppChannel, WhatsAppConfig

# TUI/CLI components (not a channel, direct agent interaction)
from .tui import CLI, CLIRenderer

__all__ = [
    # Channel architecture
    "BaseChannel",
    "ChannelManager",
    # Channels
    "TelegramChannel",
    "TelegramConfig",
    "WhatsAppChannel",
    "WhatsAppConfig",
    # TUI/CLI (direct interaction, not via bus)
    "CLI",
    "CLIRenderer",
]
