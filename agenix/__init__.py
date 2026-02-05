"""Agenix - A simple and elegant agent framework."""

__version__ = "0.2.0"

from .core import (
    Agent,
    AgentConfig,
    LLMProvider,
    LiteLLMProvider,
    get_provider,
    SessionManager,
    Settings,
    get_default_model,
    ensure_config_dir,
    # Messages
    Message,
    UserMessage,
    AssistantMessage,
    ToolResultMessage,
    TextContent,
    ImageContent,
    ToolCall,
    Usage,
    # Events
    Event,
)

from .tools import (
    Tool,
    ToolResult,
    ReadTool,
    WriteTool,
    EditTool,
    BashTool,
    GrepTool,
    GlobTool,
)

# Services
from .extensions.builtin.memory.service import MemoryStore
from .extensions.builtin.heartbeat.service import HeartbeatService, DEFAULT_HEARTBEAT_INTERVAL_S, HEARTBEAT_PROMPT
from .extensions.builtin.cron.service import CronService
from .extensions.builtin.cron.types import CronJob, CronSchedule, CronPayload, CronJobState, CronStore
from .bus import (
    MessageBus,
    Event as BusEvent,
    AgentMessageEvent,
    AgentResponseEvent,
    CronJobEvent,
    HeartbeatEvent,
    MemoryUpdateEvent,
    SystemEvent,
)

# Channels
from .channel import (
    BaseChannel,
    ChannelManager,
    TelegramChannel,
    TelegramConfig,
    WhatsAppChannel,
    WhatsAppConfig,
    CLI,
    CLIRenderer,
)

__all__ = [
    # Core
    "Agent",
    "AgentConfig",
    "LLMProvider",
    "LiteLLMProvider",
    "get_provider",
    "SessionManager",
    "Settings",
    "get_default_model",
    "ensure_config_dir",
    # Messages
    "Message",
    "UserMessage",
    "AssistantMessage",
    "ToolResultMessage",
    "TextContent",
    "ImageContent",
    "ToolCall",
    "Usage",
    "Event",
    # Tools
    "Tool",
    "ToolResult",
    "ReadTool",
    "WriteTool",
    "EditTool",
    "BashTool",
    "GrepTool",
    "GlobTool",
    # Services
    "MemoryStore",
    "HeartbeatService",
    "DEFAULT_HEARTBEAT_INTERVAL_S",
    "HEARTBEAT_PROMPT",
    "CronService",
    "CronJob",
    "CronSchedule",
    "CronPayload",
    "CronJobState",
    "CronStore",
    # Bus
    "MessageBus",
    "BusEvent",
    "AgentMessageEvent",
    "AgentResponseEvent",
    "CronJobEvent",
    "HeartbeatEvent",
    "MemoryUpdateEvent",
    "SystemEvent",
    # Channels
    "BaseChannel",
    "ChannelManager",
    "TelegramChannel",
    "TelegramConfig",
    "WhatsAppChannel",
    "WhatsAppConfig",
    "CLI",
    "CLIRenderer",
]

