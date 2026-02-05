"""Event types for the message bus."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


@dataclass
class BusEvent:
    """Base event class for the message bus."""
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentMessageEvent(BusEvent):
    """Event when agent needs to process a message."""
    message: str = ""
    session_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    kind: Literal["agent_message"] = "agent_message"


@dataclass
class AgentResponseEvent(BusEvent):
    """Event when agent produces a response."""
    response: str = ""
    session_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    kind: Literal["agent_response"] = "agent_response"


@dataclass
class CronJobEvent(BusEvent):
    """Event when a cron job is triggered."""
    job_id: str = ""
    job_name: str = ""
    message: str = ""
    deliver: bool = False
    channel: str | None = None
    to: str | None = None
    kind: Literal["cron_job"] = "cron_job"


@dataclass
class HeartbeatEvent(BusEvent):
    """Event when heartbeat is triggered."""
    prompt: str = ""
    has_content: bool = True
    kind: Literal["heartbeat"] = "heartbeat"


@dataclass
class MemoryUpdateEvent(BusEvent):
    """Event when memory is updated."""
    scope: Literal["today", "long_term"] = "today"
    content: str = ""
    kind: Literal["memory_update"] = "memory_update"


@dataclass
class SystemEvent(BusEvent):
    """General system event."""
    event_type: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    kind: Literal["system"] = "system"


# Union type for all events
Event = AgentMessageEvent | AgentResponseEvent | CronJobEvent | HeartbeatEvent | MemoryUpdateEvent | SystemEvent
