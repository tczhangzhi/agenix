"""Message types for agent communication."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Union

if TYPE_CHECKING:
    from ..tools.base import ToolResult


@dataclass
class TextContent:
    """Text content block."""
    type: Literal["text"] = "text"
    text: str = ""


@dataclass
class ImageContent:
    """Image content block."""
    type: Literal["image"] = "image"
    # {type: "base64", media_type: "...", data: "..."}
    source: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReasoningContent:
    """Reasoning content block."""
    type: Literal["reasoning"] = "reasoning"
    text: str = ""
    reasoning_id: Optional[str] = None


@dataclass
class ToolCall:
    """Tool call from assistant."""
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class Usage:
    """Token usage statistics."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    total_cost: float = 0.0


@dataclass
class UserMessage:
    """User message."""
    role: Literal["user"] = "user"
    content: Union[str, List[Union[TextContent, ImageContent]]] = ""
    timestamp: float = field(
        default_factory=lambda: datetime.now().timestamp())


@dataclass
class AssistantMessage:
    """Assistant message with tool calls and metadata."""
    role: Literal["assistant"] = "assistant"
    content: Union[str, List[Union[TextContent, ReasoningContent, ToolCall]]] = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    model: str = ""
    usage: Optional[Usage] = None
    stop_reason: Optional[str] = None  # "stop", "tool_use", "length", "error"
    timestamp: float = field(
        default_factory=lambda: datetime.now().timestamp())


@dataclass
class ToolResultMessage:
    """Tool execution result."""
    role: Literal["tool"] = "tool"
    tool_call_id: str = ""
    name: str = ""
    content: Union[str, List[Union[TextContent, ImageContent]]] = ""
    is_error: bool = False
    timestamp: float = field(
        default_factory=lambda: datetime.now().timestamp())


@dataclass
class SystemMessage:
    """System message (for context)."""
    role: Literal["system"] = "system"
    content: str = ""


# Union type for all message types
Message = Union[UserMessage, AssistantMessage,
                ToolResultMessage, SystemMessage]


@dataclass
class Context:
    """Conversation context."""
    system_prompt: Optional[str] = None
    messages: List[Message] = field(default_factory=list)
    tools: List[Dict[str, Any]] = field(default_factory=list)


# Event types for agent streaming
@dataclass
class AgentEvent:
    """Base class for agent events."""
    type: str
    timestamp: float = field(
        default_factory=lambda: datetime.now().timestamp())


@dataclass
class AgentStartEvent(AgentEvent):
    """Agent started processing."""
    type: Literal["agent_start"] = "agent_start"


@dataclass
class AgentEndEvent(AgentEvent):
    """Agent finished processing."""
    type: Literal["agent_end"] = "agent_end"
    messages: List[Message] = field(default_factory=list)


@dataclass
class TurnStartEvent(AgentEvent):
    """Turn started."""
    type: Literal["turn_start"] = "turn_start"


@dataclass
class TurnEndEvent(AgentEvent):
    """Turn ended."""
    type: Literal["turn_end"] = "turn_end"
    message: Optional[AssistantMessage] = None
    tool_results: List[ToolResultMessage] = field(default_factory=list)


@dataclass
class MessageStartEvent(AgentEvent):
    """Message streaming started."""
    type: Literal["message_start"] = "message_start"
    message: Optional[AssistantMessage] = None


@dataclass
class MessageUpdateEvent(AgentEvent):
    """Message content updated."""
    type: Literal["message_update"] = "message_update"
    message: Optional[AssistantMessage] = None
    delta: str = ""


@dataclass
class MessageEndEvent(AgentEvent):
    """Message streaming ended."""
    type: Literal["message_end"] = "message_end"
    message: Optional[AssistantMessage] = None


@dataclass
class ToolExecutionStartEvent(AgentEvent):
    """Tool execution started."""
    type: Literal["tool_execution_start"] = "tool_execution_start"
    tool_call_id: str = ""
    tool_name: str = ""
    args: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReasoningStartEvent(AgentEvent):
    """Reasoning started."""
    type: Literal["reasoning_start"] = "reasoning_start"
    reasoning_id: str = ""


@dataclass
class ReasoningUpdateEvent(AgentEvent):
    """Reasoning content updated."""
    type: Literal["reasoning_update"] = "reasoning_update"
    reasoning_id: str = ""
    delta: str = ""


@dataclass
class ReasoningEndEvent(AgentEvent):
    """Reasoning ended."""
    type: Literal["reasoning_end"] = "reasoning_end"
    reasoning_id: str = ""
    content: str = ""


@dataclass
class ToolExecutionUpdateEvent(AgentEvent):
    """Tool execution progress update."""
    type: Literal["tool_execution_update"] = "tool_execution_update"
    tool_call_id: str = ""
    tool_name: str = ""
    partial_result: Any = None


@dataclass
class ToolExecutionEndEvent(AgentEvent):
    """Tool execution completed."""
    type: Literal["tool_execution_end"] = "tool_execution_end"
    tool_call_id: str = ""
    tool_name: str = ""
    result: Union[str, "ToolResult", Any] = None  # Make it clear we expect ToolResult objects
    is_error: bool = False


# Union type for all event types
Event = Union[
    AgentStartEvent,
    AgentEndEvent,
    TurnStartEvent,
    TurnEndEvent,
    MessageStartEvent,
    MessageUpdateEvent,
    MessageEndEvent,
    ReasoningStartEvent,
    ReasoningUpdateEvent,
    ReasoningEndEvent,
    ToolExecutionStartEvent,
    ToolExecutionUpdateEvent,
    ToolExecutionEndEvent,
]
