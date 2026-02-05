"""Extensions package - Tool registry and event types."""

from .types import (
    EventType,
    Event,
    CancellableEvent,
    SessionStartEvent,
    SessionEndEvent,
    SessionShutdownEvent,
    BeforeAgentStartEvent,
    AgentStartEvent,
    AgentEndEvent,
    TurnStartEvent,
    TurnEndEvent,
    ToolCallEvent,
    ToolResultEvent,
    UserInputEvent,
    ContextEvent,
    BeforeCompactEvent,
    CompactEvent,
    ExtensionContext,
    ToolDefinition,
    CommandDefinition,
    EventHandler,
    ExtensionAPI,
    ExtensionSetup,
    LoadedExtension,
)
from .loader import (
    ExtensionLoaderAPI,
    discover_extensions,
    load_extension,
    discover_and_load_extensions,
)
from .runner import ExtensionRunner

__all__ = [
    # Types
    "EventType",
    "Event",
    "CancellableEvent",
    "SessionStartEvent",
    "SessionEndEvent",
    "SessionShutdownEvent",
    "BeforeAgentStartEvent",
    "AgentStartEvent",
    "AgentEndEvent",
    "TurnStartEvent",
    "TurnEndEvent",
    "ToolCallEvent",
    "ToolResultEvent",
    "UserInputEvent",
    "ContextEvent",
    "BeforeCompactEvent",
    "CompactEvent",
    "ExtensionContext",
    "ToolDefinition",
    "CommandDefinition",
    "EventHandler",
    "ExtensionAPI",
    "ExtensionSetup",
    "LoadedExtension",
    # Loader
    "ExtensionLoaderAPI",
    "discover_extensions",
    "load_extension",
    "discover_and_load_extensions",
    # Runner
    "ExtensionRunner",
]

